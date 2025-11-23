from django.urls import path
from . import views

urlpatterns = [
    
    path('', views.home, name='homepage'),
    path('adminlogin/', views.adminlogin, name='Admin_Login'),
    path('alog/', views.alog, name='alog'),
    path('adminpage/', views.admin_page, name='admin_page'),
    path('media/products/list/', views.list_media_products, name='list_media_products'),

    
    path('add/', views.add_product, name='add_product'),
    path('edit/<int:pk>/', views.edit_product, name='edit_product'),
    path('delete/<int:pk>/', views.delete_product, name='delete_product'),

    
    path('user_register/', views.user_register, name='user_register'),
    path('user_login/', views.user_login, name='user_login'),
    path('userlog/', views.userlog, name='userlog'),
    path('user_logout/', views.user_logout, name='user_logout'),
    

    
    path('cart/', views.cart_view, name='cart_view'),
    path('cart/add/', views.add_to_cart, name='add_to_cart'),
    path('cart/update/<int:pk>/', views.update_cart, name='update_cart'),
    path('cart/remove/<int:pk>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/checkout/', views.checkout, name='checkout'),



    path('checkout_view/', views.checkout_view, name='checkout'),
    path('checkout/success/', views.checkout_success, name='checkout_success'),


    path('orders/history/', views.order_history_view, name='order_history'),
    path('orders/<int:order_id>/invoice/', views.invoice_view, name='invoice'),
    path('admin/products/', views.admin_product_gallery, name='admin_products'),
    path('invoice/',views.invoice_view,name='latest_invoice'),
    path('ajax/add-category/', views.add_category_ajax, name='add_category_ajax'),




]
