import traceback
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.core.exceptions import ValidationError
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib import messages
from .models import Product, Category, UserRegister  
from .models import Order, OrderItem
from django.db import transaction, IntegrityError
from django.contrib.auth.decorators import login_required,user_passes_test
from .models import Order, OrderItem
from django.contrib.auth.models import User
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import authenticate, login, logout
from django.db.models import Q
from django.conf import settings
import random
import os
from pathlib import Path
from functools import wraps

# Custom decorator that checks staff status
# Note: Use with @login_required(login_url='Admin_Login') for authentication
def staff_only(view_func):
    
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_staff:
            # Redirect to admin login if not staff (even if authenticated)
            return redirect(reverse('Admin_Login') + '?next=' + request.path)
        return view_func(request, *args, **kwargs)
    return _wrapped_view





def _get_cart_dict(request):
    
    cart = request.session.get('cart')
    if cart is None:
        cart = {}
        request.session['cart'] = cart
    return cart

def product_to_dict(p: Product) -> dict:
    return {
        'id': p.id,
        'title': p.title,
        'description': p.description,
        'image_url': p.image.url if getattr(p,'image',None) else '',
        'price': str(getattr(p, 'price', Decimal('0.00'))),   # string OK for JS
        'category_id': p.category.id if p.category else None,
        'category_name': p.category.name if p.category else '',
    }



def home(request):
    query = (request.GET.get('q') or '').strip()
    products = Product.objects.all().order_by('-created_at')

    if query:
        products = products.filter(
            Q(title__icontains=query) | Q(description__icontains=query) | Q(category__name__icontains=query)
        ).distinct()

    # Choose a random background image from MEDIA_ROOT/products/
    bg_url = ''
    try:
        media_root = Path(settings.MEDIA_ROOT)
        products_dir = media_root / 'products'
        allowed_exts = ('.jpg', '.jpeg', '.png', '.webp', '.gif')
        files = []
        if products_dir.exists() and products_dir.is_dir():
            for p in products_dir.iterdir():
                if p.is_file() and p.suffix.lower() in allowed_exts:
                    files.append(p.relative_to(media_root).as_posix())
        if files:
            chosen = random.choice(files)
            bg_url = settings.MEDIA_URL.rstrip('/') + '/' + chosen
    except Exception:
        bg_url = ''

    return render(request, 'Firstview.html', {
        'products': products,
        'search_query': query,
        'bg_image_url': bg_url,
    })



def adminlogin(request):

    return render(request, 'Admin.html')


def alog(request):
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        
        # Authenticate the user
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_active:
            # Grant staff privileges (for admin login)
            if not user.is_staff:
                user.is_staff = True
                user.save()
            # Log the user in
            login(request, user)
            # Redirect to the page they were trying to access, or admin page
            next_url = request.GET.get('next') or request.POST.get('next') or reverse('admin_page')
            return redirect(next_url)
        else:
            # Invalid credentials
            return render(request, 'Admin.html', {'error': 'Invalid username or password'})
    
    # GET request - show login page
    return render(request, 'Admin.html')

def contact(request):
    return render(request,'contact.html')


@login_required(login_url='Admin_Login')
@staff_only

def admin_page(request):
    products = Product.objects.all().order_by('-created_at')
    categories = Category.objects.all().order_by('name')
    return render(request, 'Adminpage.html', {'products': products, 'categories': categories})

@login_required(login_url='Admin_Login')
@staff_only
@require_POST

def add_product(request):

    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)

    try:
        title = (request.POST.get('title') or '').strip() or 'Untitled'
        description = (request.POST.get('description') or '').strip()
        image = request.FILES.get('image')
        image_from_media = (request.POST.get('image_from_media') or '').strip()
        price_raw = request.POST.get('price', None)
        category_id = request.POST.get('category')
        p = Product(title=title, description=description)
        
        # Handle category
        if category_id:
            try:
                p.category = Category.objects.get(pk=int(category_id))
            except (Category.DoesNotExist, ValueError, TypeError):
                p.category = None
        else:
            p.category = None

        if price_raw is not None and price_raw != '':
            try:
                p.price = Decimal(str(price_raw))
                if p.price < 0:
                    p.price = abs(p.price)
            except (InvalidOperation, ValueError, TypeError):
                p.price = getattr(p, 'price', Decimal('0.00'))


        if image:
            p.image = image
        elif image_from_media:
            # assign an existing media file by relative storage path
            # ensure it stays inside MEDIA_ROOT
            rel = image_from_media.lstrip('/')
            # normalize to forward slashes
            rel = rel.replace('\\', '/')
            # only allow under products/
            if not rel.startswith('products/'):
                return JsonResponse({'ok': False, 'error': 'Invalid media path'}, status=400)
            p.image.name = rel

       
        p.full_clean()
        p.save()
        return JsonResponse({'ok': True, 'product': product_to_dict(p)})
    except ValidationError as e:
        return JsonResponse({'ok': False, 'errors': e.message_dict}, status=400)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e), 'trace': traceback.format_exc()}, status=500)


@login_required(login_url='Admin_Login')
@staff_only
@require_POST

def edit_product(request, pk):
  
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)

    p = get_object_or_404(Product, pk=pk)
    try:
       
        title = (request.POST.get('title') or '').strip() or 'Untitled'
        description = (request.POST.get('description') or '').strip()
        category_id = request.POST.get('category')

        price_raw = request.POST.get('price', None)
        
        # Handle category
        if category_id:
            try:
                p.category = Category.objects.get(pk=int(category_id))
            except (Category.DoesNotExist, ValueError, TypeError):
                p.category = None
        else:
            p.category = None
        if price_raw is not None and price_raw != '':
            try:
                # convert to Decimal using string to preserve precision
                p.price = Decimal(str(price_raw))
                # optionally enforce non-negative
                if p.price < 0:
                    p.price = abs(p.price)
            except (InvalidOperation, ValueError, TypeError):
                # keep existing price on parse error (or set to 0.00 if no existing)
                p.price = getattr(p, 'price', Decimal('0.00'))
        else:
            # If no price provided in form, keep existing value (do nothing)
            p.price = getattr(p, 'price', Decimal('0.00'))

        # Image handling
        img = request.FILES.get('image')
        image_from_media = (request.POST.get('image_from_media') or '').strip()
        if img:
            # remove old file (best-effort) and assign new
            if getattr(p, 'image', None):
                try:
                    p.image.delete(save=False)
                except Exception:
                    pass
            p.image = img
        elif image_from_media:
            # assign existing file path; do not delete old file on storage if path is same
            rel = image_from_media.lstrip('/')
            rel = rel.replace('\\', '/')
            if not rel.startswith('products/'):
                return JsonResponse({'ok': False, 'error': 'Invalid media path'}, status=400)
            # optionally delete old
            if getattr(p, 'image', None) and p.image.name != rel:
                try:
                    p.image.delete(save=False)
                except Exception:
                    pass
            p.image.name = rel

        if request.POST.get('image-clear') == 'true':
            if getattr(p, 'image', None):
                try:
                    p.image.delete(save=False)
                except Exception:
                    pass
            p.image = None

        # Assign other fields
        p.title = title
        p.description = description

        # Validate and save
        p.full_clean()
        p.save()

        return JsonResponse({'ok': True, 'product': product_to_dict(p)})
    except ValidationError as e:
        return JsonResponse({'ok': False, 'errors': e.message_dict}, status=400)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e), 'trace': traceback.format_exc()}, status=500)


@login_required(login_url='Admin_Login')
@staff_only
@require_POST
def add_category_ajax(request):
  
    try:
        name = (request.POST.get('name') or '').strip()
        if not name:
            return JsonResponse({'ok': False, 'error': 'empty_name'}, status=400)

        # prevent duplicates (case-insensitive)
        existing = Category.objects.filter(name__iexact=name).first()
        if existing:
            return JsonResponse({'ok': False, 'error': 'exists', 'category': {'id': existing.id, 'name': existing.name}}, status=409)

        cat = Category.objects.create(name=name)
        return JsonResponse({'ok': True, 'category': {'id': cat.id, 'name': cat.name}})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)



@login_required(login_url='Admin_Login')
@staff_only
@require_POST

def delete_product(request, pk):
 
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)

    p = get_object_or_404(Product, pk=pk)
    try:
        if getattr(p, 'image', None):
            try:
                p.image.delete(save=False)
            except Exception:
                pass
        p.delete()
        return JsonResponse({'ok': True, 'deleted': True})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)

def user_register(request):
    """Register new user (creates both Django User and your UserRegister record)."""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()

        # 1️⃣ Validation
        if not phone or not password:
            return render(request, 'User_register.html', {'error': 'Phone and password are required!'})

        if password != confirm_password:
            return render(request, 'User_register.html', {'error': 'Passwords do not match!'})

        # 2️⃣ Prevent duplicates (based on phone)
        if User.objects.filter(username=phone).exists():
            return render(request, 'User_register.html', {'error': 'Phone number already exists!'})

        try:
            # 3️⃣ Create Django auth user
            user = User.objects.create_user(
                username=phone,
                password=password,
                email=email,
                first_name=name
            )

            # 4️⃣ Also create entry in your UserRegister model (optional)
            UserRegister.objects.create(
                name=name,
                email=email,
                phone=phone,
                password=password  # (keep only if you really need it — plain text!)
            )

            # 5️⃣ Auto-login after registration
            login(request, user)
            return redirect('homepage')

        except IntegrityError:
            return render(request, 'User_register.html', {'error': 'Something went wrong — try again!'})

    return render(request, 'User_register.html')

def user_login(request):
  
    if request.method == 'POST':
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '').strip()
        # we will use phone as username on Django's User model
        user = authenticate(request, username=phone, password=password)
        if user is not None and user.is_active:
            login(request, user)
            # Optional: you previously stored name in session; not needed now.
            # Redirect to 'next' if present
            next_url = request.GET.get('next') or request.POST.get('next') or reverse('homepage')
            return redirect(next_url)
        # invalid credentials
        return render(request, 'User_login.html', {'error': 'Invalid credentials'})

    # GET
    return render(request, 'User_login.html')


def userlog(request):
    
    if request.method == 'POST':
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '').strip()

        # Validate against your custom UserRegister model (adjust fields as needed)
        qs = UserRegister.objects.filter(phone=phone, password=password)
        if not qs.exists():
            return render(request, 'User_login.html', {'error': 'Invalid credentials'})

        profile = qs.first()

        # Find or create a corresponding django.contrib.auth User
        django_user, created = User.objects.get_or_create(username=phone)
        # Optionally keep some fields in sync:
        if created:
            django_user.first_name = getattr(profile, 'name', '')[:30]
            # Do NOT set password to the profile plain-text password; instead use set_unusable_password()
            django_user.set_unusable_password()
            django_user.save()

        # Force backend so login() accepts it (only necessary when you didn't use authenticate())
        django_user.backend = 'django.contrib.auth.backends.ModelBackend'
        login(request, django_user)

        # Optionally copy profile info to session if you still need it
        request.session['name'] = getattr(profile, 'name', '')
        request.session['user_id'] = profile.id

        return redirect('homepage')

    return render(request, 'User_login.html')



def user_logout(request):
    logout(request)
    return redirect('homepage')


@login_required(login_url='user_login')
@require_POST
def add_to_cart(request):
    """
    Add product to session cart. Requires Django auth login.
    Returns JSON: { ok, cart_count, cart_total }
    """
    product_id = request.POST.get('product_id')
    if not product_id:
        return JsonResponse({'ok': False, 'error': 'Missing product_id'}, status=400)

    try:
        qty = int(request.POST.get('qty', 1))
    except (ValueError, TypeError):
        qty = 1
    if qty <= 0:
        qty = 1

    try:
        prod = Product.objects.get(pk=int(product_id))
    except (Product.DoesNotExist, ValueError):
        return JsonResponse({'ok': False, 'error': 'Product not found'}, status=404)

    # update session cart (keeps the session-cart approach)
    cart = _get_cart_dict(request)  # your helper that ensures request.session['cart'] exists
    cart[str(product_id)] = cart.get(str(product_id), 0) + qty
    request.session['cart'] = cart
    request.session.modified = True

    # compute cart_count and cart_total (sum of price * qty)
    cart_count = sum(int(v) for v in cart.values())
    cart_total = Decimal('0.00')
    for pid, q in cart.items():
        try:
            p = Product.objects.get(pk=int(pid))
            price = getattr(p, 'price', 0) or 0
            try:
                price_dec = Decimal(str(price))
            except (InvalidOperation, TypeError):
                price_dec = Decimal('0.00')
            cart_total += price_dec * Decimal(int(q))
        except Exception:
            # ignore missing products when calculating total
            continue

    # return cart_total as string so JSON serialization is stable and precise
    return JsonResponse({
        'ok': True,
        'cart_count': cart_count,
        'cart_total': str(cart_total),
    })


def cart_view(request):
    """Render cart page showing items from session cart."""
    cart = request.session.get('cart', {})
    items = []
    total = 0
    for pid, qty in cart.items():
        try:
            p = Product.objects.get(pk=int(pid))
        except Product.DoesNotExist:
            continue
        price = getattr(p, 'price', 0)  # safe if no price field
        subtotal = price * int(qty)
        total += subtotal
        items.append({
            'id': p.id,
            'title': p.title,
            'qty': int(qty),
            'price': price,
            'subtotal': subtotal,
            'image_url': p.image.url if getattr(p, 'image', None) else '',
        })
    return render(request, 'cart.html', {'cart_items': items, 'total': total})


def remove_from_cart(request, pk):
    """Remove an item from cart (expects POST)."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)

    cart = request.session.get('cart', {})
    cart.pop(str(pk), None)
    request.session['cart'] = cart
    request.session.modified = True
    return JsonResponse({'ok': True})


def update_cart(request, pk):
    """Update qty for a cart item (expects POST with 'qty')."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)

    try:
        qty = int(request.POST.get('qty', 1))
    except (ValueError, TypeError):
        qty = 1

    cart = request.session.get('cart', {})
    if str(pk) in cart:
        if qty <= 0:
            cart.pop(str(pk), None)
        else:
            cart[str(pk)] = qty
    request.session['cart'] = cart
    request.session.modified = True
    return JsonResponse({'ok': True})


def checkout(request):
   
    if request.method == 'POST':
        request.session.pop('cart', None)
        return redirect('homepage')
    # if someone GETs checkout, just show a simple page or redirect
    return redirect('cart_view')


def get_cart_items(request):

    from decimal import Decimal, ROUND_HALF_UP

    cart = request.session.get('cart', {}) or {}
    # Ensure cart is a dict; if not, reset to empty dict
    if not isinstance(cart, dict):
        cart = {}

    items = []
    total = Decimal('0.00')

    for pid, data in cart.items():
        # If data is not a mapping, treat it as a legacy qty value
        if isinstance(data, dict):
            data_map = data
        else:
            data_map = {'qty': data}

        # qty
        try:
            qty = int(data_map.get('qty', 0))
        except (TypeError, ValueError):
            qty = 0

        if qty <= 0:
            # skip zero/negative quantities
            continue

        # Try to fetch product details if not present in session (legacy cart format)
        product_obj = None
        try:
            product_obj = Product.objects.get(pk=int(pid))
        except Exception:
            product_obj = None

        # price -> Decimal (handle Decimal, float, int, str safely)
        try:
            if 'price' in data_map and data_map.get('price') not in (None, ''):
                raw_price = data_map.get('price')
            else:
                raw_price = getattr(product_obj, 'price', '0') if product_obj else '0'
            price = Decimal(str(raw_price)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except Exception:
            price = Decimal('0.00')

        subtotal = (price * qty).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # title and image_url: prefer cart data, else fallback to product
        title = data_map.get('title', '')
        if title is None:
            title = ''
        if not title and product_obj:
            title = getattr(product_obj, 'title', '') or ''
        title = str(title)[:255]

        image_url = data_map.get('image_url', '')
        if image_url is None:
            image_url = ''
        if not image_url and product_obj and getattr(product_obj, 'image', None):
            try:
                image_url = product_obj.image.url
            except Exception:
                image_url = ''
        image_url = str(image_url)

        items.append({
            'id': pid,
            'title': title,
            'image_url': image_url,
            'price': str(price),
            'qty': qty,
            'subtotal': subtotal,
        })
        total += subtotal

    total = total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return items, total





@require_http_methods(["GET", "POST"])
def checkout_view(request):
    cart_items, cart_total = get_cart_items(request)
    if not cart_items:
        messages.info(request, "Your cart is empty.")
        return redirect('homepage')

    if request.method == 'POST':
        # read form fields (pincode optional)
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        pincode = request.POST.get('pincode', '').strip()
        address = request.POST.get('address', '').strip()
        note = request.POST.get('note', '').strip()

        # basic server-side validation
        if not name or not email:
            messages.error(request, "Name and email are required.")
            # re-render checkout with previously entered values
            return render(request, 'checkout.html', {
                'cart_items': cart_items,
                'total': "%.2f" % cart_total,
                'prefill': {
                    'name': name,
                    'email': email,
                    'phone': phone,
                    'pincode': pincode,
                    'address': address,
                    'note': note,
                },
            })

        # Save order + items atomically
        with transaction.atomic():
            order = Order.objects.create(
                user=request.user if request.user.is_authenticated else None,
                name=name,
                email=email,
                phone=phone,
                address=address,
                total=cart_total,  # keep Decimal for DB
                note=note or ""
            )

            for it in cart_items:
                OrderItem.objects.create(
                    order=order,
                    product_id=str(it.get('id', '')),
                    title=it.get('title', '')[:255],
                    price=it.get('price'),   # Decimal -> DB
                    qty=it.get('qty', 1),
                    subtotal=it.get('subtotal')  # Decimal -> DB
                )

        # clear cart and save a brief summary for the success page
        request.session['cart'] = {}

        # Convert Decimal subtotals and total to rounded floats for JSON-safe session storage
        latest_order = {
            'id': order.id,
            'name': order.name,
            'email': order.email,
            'items': [
                {
                    'title': it.get('title'),
                    'qty': int(it.get('qty') or 0),
                    'subtotal': float(round(it.get('subtotal') or Decimal('0.00'), 2)),
                    'image_url': it.get('image_url', '')
                } for it in cart_items
            ],
            'total': float(round(cart_total or Decimal('0.00'), 2))
        }
        request.session['latest_order'] = latest_order
        request.session.modified = True

        return redirect('checkout_success')

    # GET -> render checkout page
    return render(request, 'checkout.html', {
        'cart_items': cart_items,
        'total': "%.2f" % cart_total
    })

def checkout_success(request):
    order_summary = request.session.pop('latest_order', None)
    return render(request, 'checkout_success.html', {'order': order_summary})




@login_required(login_url='user_login')
def order_history_view(request):
    """Show all orders for the logged-in user"""
    orders = Order.objects.filter(user=request.user).order_by('-created_at')

    # You can prefetch related items for efficiency
    orders = orders.prefetch_related('items')

    return render(request, 'order_history.html', {'orders': orders})



@login_required(login_url='user_login')
def invoice_view(request, order_id):
   
    order = get_object_or_404(Order, pk=order_id)

    # If Order.user is nullable and you allow anonymous orders, handle accordingly.
    if order.user is None or order.user != request.user:
        # if you want to allow admins to view, add a staff check
        if not (request.user.is_staff or request.user.is_superuser):
            return HttpResponseForbidden("You don't have permission to view this invoice.")

    # If you stored summary in session and want to use session latest_order for guests,
    # you would adapt this. Here we assume authenticated users created orders.
    return render(request, 'invoice.html', {'order': order})




@login_required(login_url='Admin_Login')
@staff_only
def admin_product_gallery(request):
    """
    Admin-only product gallery page (shows products + purchase history).
    """
    products = Product.objects.all().order_by('-id')
    # show recent orders (all orders visible to admin)
    orders = Order.objects.all().order_by('-created_at')  # change ordering if needed

    return render(request, 'admin_product_gallery.html', {
        'products': products,
        'orders': orders,
    })


@login_required(login_url='Admin_Login')
@staff_only
@require_http_methods(["GET"])
def list_media_products(request):
    """
    Return JSON list of files under MEDIA_ROOT/products/ (name and url).
    """
    media_root = Path(settings.MEDIA_ROOT)
    products_dir = media_root / 'products'
    files = []
    try:
        if products_dir.exists() and products_dir.is_dir():
            for root, _, filenames in os.walk(products_dir):
                for fn in filenames:
                    # accept common image extensions
                    lower = fn.lower()
                    if not any(lower.endswith(ext) for ext in ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')):
                        continue
                    full_path = Path(root) / fn
                    rel_path = full_path.relative_to(media_root).as_posix()
                    files.append({
                        'name': fn,
                        'path': rel_path,  # relative path to MEDIA_ROOT
                        'url': settings.MEDIA_URL.rstrip('/') + '/' + rel_path,
                    })
        return JsonResponse({'ok': True, 'files': files})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)
