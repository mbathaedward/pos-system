from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from inventory.models import product as Product
from .models import Cart


@login_required(login_url="/user/login")
def cart_add(request, id, qty):
    cart = Cart(request)

    try:
        product = Product.objects.get(barcode=id)
    except Product.DoesNotExist:
        return redirect("product_not_found")

    try:
        qty = int(qty)
        if qty <= 0:
            qty = 1
    except ValueError:
        qty = 1

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
        cart.add(product=product)
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