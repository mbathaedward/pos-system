from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from inventory.models import product as Product
from .models import Cart
from django.contrib import messages


@login_required(login_url="/user/login")
def cart_add(request, id, qty):
    cart = Cart(request)
    try:
        product = Product.objects.get(barcode=id)
    except Product.DoesNotExist:
        messages.error(request, "Product does not exist!")
        return redirect("register")

    try:
        qty = int(qty)
        if qty <= 0:
            qty = 1
    except ValueError:
        qty = 1
        
    print(product.__dict__)
    stock = product.qty or 0
    already_in_cart = cart.cart.get(str(product.barcode), {}).get('quantity', 0)

    if already_in_cart + qty > stock:
        messages.error(request, f"Only {stock} items available. You already have {already_in_cart} in cart!")
        
        return redirect("register")

    cart.add(product=product, quantity=qty)
    return redirect('register')


@login_required(login_url="/user/login")
def item_clear(request, id):
    cart = Cart(request)
    try:
        product = Product.objects.get(barcode=id)
        cart.remove(product)
    except Product.DoesNotExist:
        pass
    return redirect("cart_detail")


@login_required(login_url="/user/login")
def item_increment(request, id):
    cart = Cart(request)
    try:
        product = Product.objects.get(barcode=id)
        stock = product.qty or 0
        already_in_cart = cart.cart.get(str(product.barcode), {}).get('quantity', 0)

        if already_in_cart + 1 > stock:
            messages.error(request, f"Only {stock} items available in the store!")
            return redirect("cart_detail")

        cart.add(product=product, quantity=1)
    except Product.DoesNotExist:
        pass
    return redirect("cart_detail")


@login_required(login_url="/user/login")
def item_decrement(request, id):
    cart = Cart(request)
    try:
        product = Product.objects.get(barcode=id)
        cart.decrement(product=product)
    except Product.DoesNotExist:
        pass
    return redirect("cart_detail")


@login_required(login_url="/user/login")
def cart_clear(request):
    cart = Cart(request)
    cart.clear()
    return redirect('register')