from django.contrib import admin
from .models import Product
from django.contrib import admin
from .models import Order, OrderItem

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('title', 'created_at')




class OrderItemInline(admin.TabularInline):
    model = OrderItem
    readonly_fields = ('product_id', 'title', 'price', 'qty', 'subtotal')
    extra = 0

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'email', 'total', 'created_at')
    inlines = [OrderItemInline]
    readonly_fields = ('created_at',)

