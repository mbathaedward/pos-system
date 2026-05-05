import json
import pandas as pd
from datetime import datetime, timedelta

from django.shortcuts import redirect, render
from django.http import Http404
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django import forms
from escpos.printer import Usb

from cart.models import Cart
from .models import transaction


class DateSelector(forms.Form):
    start_date = forms.DateField(widget=forms.SelectDateWidget())
    end_date   = forms.DateField(widget=forms.SelectDateWidget())


class printer:
    printer = None

    def printReceipt(printText, times=0, *args, **kwargs):
        try:
            if printer.printer:
                printer.printer.text(printText)
                printer.printer.text(f"\nPrint Time: {datetime.now():%Y-%m-%d %H:%M}\n\n\n")
        except Exception as e:
            printer.connectPrinter()
            if times < 3:
                printer.printReceipt(printText, times + 1)

    def connectPrinter():
        try:
            printer.printer = Usb(eval(settings.PRINTER_VENDOR_ID), eval(settings.PRINTER_PRODUCT_ID))
        except Exception as e:
            print(e)
            printer.printer = None


def transactionReceipt(request, transNo):
    try:
        receipt = transaction.objects.get(transaction_id=transNo).receipt
        return render(request, 'receiptView.html', context={'receipt': receipt, 'transNo': transNo})
    except transaction.DoesNotExist:
        raise Http404("No Transactions Found!!!")


def transactionPrintReceipt(request, transNo):
    try:
        receipt = transaction.objects.get(transaction_id=transNo).receipt
        if printer.printer is None:
            printer.connectPrinter()
            print("Connecting Printer")
        if printer.printer:
            printer.printReceipt(receipt)
        return redirect(f'/transaction_receipt/{transNo}/')
    except Exception as e:
        print(e)
        return redirect('register')


@login_required(login_url="/user/login/")
def transactionView(request, transNo=None):
    end_date   = datetime.now().date()
    start_date = datetime.now().date() - timedelta(7)
    form = DateSelector(initial={'end_date': end_date, 'start_date': start_date})
    if request.method == "POST":
        form = DateSelector(request.POST)
        if form.is_valid():
            end_date   = form.cleaned_data['end_date']
            start_date = form.cleaned_data['start_date']
    transactions = transaction.objects.filter(
        transaction_dt__date__range=(start_date, end_date)
    ).order_by('-transaction_dt').values('transaction_dt', 'transaction_id', 'total_sale', 'payment_type')
    return render(request, 'transactions.html', context={'transactions': transactions, 'form': form})


@login_required(login_url="/user/login/")
def returnsTransaction(request):
    Cart(request).returns()
    return redirect('register')


@login_required(login_url="/user/login/")
def suspendTransaction(request):
    if Cart(request).isNotEmpty():
        if "Cart_Sessions" in request.session.keys():
            request.session["Cart_Sessions"][datetime.now().strftime('%Y%m%d%H%M%S%f')] = request.session[settings.CART_SESSION_ID]
            request.session.modified = True
        else:
            request.session["Cart_Sessions"] = {}
            request.session["Cart_Sessions"][datetime.now().strftime('%Y%m%d%H%M%S%f')] = request.session[settings.CART_SESSION_ID]
    return redirect("cart_clear")


@login_required(login_url="/user/login/")
def recallTransaction(request, recallTransNo=None):
    if Cart(request).isNotEmpty():
        return redirect("suspend_transaction")
    if recallTransNo:
        request.session[settings.CART_SESSION_ID] = request.session["Cart_Sessions"][recallTransNo]
        del request.session["Cart_Sessions"][recallTransNo]
        request.session.modified = True
    elif "Cart_Sessions" in request.session.keys() and len(request.session["Cart_Sessions"]):
        return render(request, "recallTransaction.html", context={"obj_rt": request.session["Cart_Sessions"].keys()})
    return redirect("register")


@login_required(login_url="/user/login/")
def endTransactionReceipt(request, transNo):
    try:
        if request.GET["type"] == "cash":
            change = float(request.GET["value"]) - float(request.GET["total"])
            change = f"""<table class="table text-white h3 p-0 m-0">
                            <tr>
                                <td class="text-left pl-5"> Total : </td>
                                <td class="text-right pr-5"> {request.GET["total"]} ksh</td>
                            </tr>
                            <tr>
                                <td class="text-left pl-5"> Cash : </td>
                                <td class="text-right pr-5"> {request.GET["value"]} ksh</td>
                            </tr>
                            <tr class="h1 badge-danger">
                                <td style="padding-top:15px"> Change : </td>
                                <td style="padding-top:15px"> {change * (-1):.2f} ksh</td>
                            </tr>
                        </table>"""
        elif request.GET["type"] == "card":
            change = f"""<table class="table text-white h3 p-0 m-0">
                            <tr>
                                <td class="text-left pl-5"> Total : </td>
                                <td class="text-right pr-5"> {request.GET["total"]} $</td>
                                <td class="text-left pl-5"> Card : </td>
                                <td class="text-right pr-5"> {request.GET["value"]}</td>
                            </tr>
                        </table>
                        <div class="h1 badge-danger p-3">CARD TRANSACTION</div>"""

        obj = transaction.objects.get(transaction_id=transNo)
        return render(request, 'endTransaction.html', context={'receipt': obj.receipt, 'change': change})
    except transaction.DoesNotExist:
        raise Http404("No Transactions Found!!!")


@login_required(login_url="/user/login/")
def endTransaction(request, type, value):
    try:
        return_transaction = None
        cart  = request.session[settings.CART_SESSION_ID]
        total = round(pd.DataFrame(cart).T["line_total"].astype(float).sum(), 2)
        if type == "card":
            if value == "EBT":
                return_transaction = addTransaction(request.user, "EBT", total, cart, total)
            elif value == "DEBIT_CREDIT":
                return_transaction = addTransaction(request.user, "DEBIT/CREDIT", total, cart, total)
        elif type == "cash":
            value = round(float(value), 2)
            if value >= total:
                return_transaction = addTransaction(request.user, "CASH", total, cart, value)
        if return_transaction:
            Cart(request).clear()
            # FIX 1: use return_transaction.total_sale so the redirect
            # carries the corrected total, not the old line_total sum
            return redirect(f"/endTransaction/{return_transaction.transaction_id}/?type={type}&value={value}&total={return_transaction.total_sale}")
        return redirect("register")
    except Exception as e:
        print(e, type, value, request.user)
        return redirect("register")
    

def addTransaction(user, payment_type, total, cart, value):
    transaction_id = datetime.now().strftime('%Y%m%d%H%M%S%f')

    # Build DataFrame
    try:
        cart_df = pd.DataFrame(cart).T.reset_index(drop=True)
    except Exception:
        cart_df = pd.DataFrame()

    cart_df.index = cart_df.index + 1

    # Safe default columns
    defaults = {
        "name": "", "barcode": "", "quantity": 0,
        "price": 0, "tax": "", "tax_value": 0,
        "deposit_value": 0, "deposit": 0,
    }
    for col, default in defaults.items():
        if col not in cart_df.columns:
            cart_df[col] = default

    # Safe type conversion
    cart_df["quantity"]      = pd.to_numeric(cart_df["quantity"], errors="coerce").fillna(0)
    cart_df["price"]         = pd.to_numeric(cart_df["price"], errors="coerce").fillna(0)
    cart_df["tax_value"]     = pd.to_numeric(cart_df["tax_value"], errors="coerce").fillna(0)
    cart_df["deposit_value"] = pd.to_numeric(cart_df["deposit_value"], errors="coerce").fillna(0)

    cart_df["deposit_display"] = cart_df["deposit_value"].apply(
        lambda x: f"{float(x):.2f}" if float(x or 0) > 0 else ""
    )

    # FIX 2: calculate sub_total directly from price x quantity
    cart_df["sub_total"] = cart_df["price"] * cart_df["quantity"]

    sub_total     = round(cart_df["sub_total"].sum(), 2)
    tax_total     = round(cart_df["tax_value"].sum(), 2)
    deposit_total = round(cart_df["deposit_value"].sum(), 2)

    # FIX 3: derive total from sub_total + tax_total, not from line_total
    #total = round(sub_total + tax_total, 2)
    total = sub_total

    # Build receipt
    def safe(val):
        return "" if val is None else str(val)

    receipt_lines = []
    for _, row in cart_df.iterrows():
        # FIX 4: widen columns so price and deposit don't merge visually
        line = (
            f"{safe(row.name)+')':<3} {safe(row['name'])[:28]}".ljust(settings.RECEIPT_CHAR_COUNT)
            + "\n"
            + f" {safe(row['barcode']):<13}"
              f"{int(row['quantity']):>3}"
              f"{float(row['price']):>10.2f}"
              f"{row['deposit_display']:>8}"
              f"{safe(row['tax']):>3}"
        )
        receipt_lines.append(line)

    cart_string = "\n".join(receipt_lines)
    cart_string = (
        "NAME | BARCODE QTY PRICE DP TAX".rjust(settings.RECEIPT_CHAR_COUNT)
        + f"\n{'-' * settings.RECEIPT_CHAR_COUNT}\n"
        + cart_string
    )
    cart_string = (
        f"Transaction:{transaction_id}".center(settings.RECEIPT_CHAR_COUNT)
        + f"\n{'-' * settings.RECEIPT_CHAR_COUNT}\n"
        + cart_string
    )

    #  use sub_total variable, not total - tax_total
    total_string = (
        f"Sub-Total: {sub_total}  Tax-Total: {tax_total}"
    ).center(settings.RECEIPT_CHAR_COUNT)
    total_string += "\n" + (" - " * int(settings.RECEIPT_CHAR_COUNT / 3)) + "\n"
    total_string += f"{'TOTAL SALE':>10}: {round(total, 2)}".rjust(settings.RECEIPT_CHAR_COUNT)
    total_string += "\n" + f"{str(payment_type):>10}: ksh {round(value, 2):.2f}".rjust(settings.RECEIPT_CHAR_COUNT)
    total_string += "\n" + f"{'CHANGE':>10}: ksh {round(value - total, 2):.2f}".rjust(settings.RECEIPT_CHAR_COUNT)

    receipt = (
        settings.RECEIPT_HEADER + "\n\n"
        + cart_string
        + f"\n{'-' * settings.RECEIPT_CHAR_COUNT}\n"
        + total_string
        + "\n\n"
        + settings.RECEIPT_FOOTER
    )
    receipt = "\n".join([i.center(settings.RECEIPT_CHAR_COUNT) for i in receipt.splitlines()])

    return transaction.objects.create(
        transaction_id=transaction_id,
        transaction_dt=datetime.strptime(transaction_id[:-6], '%Y%m%d%H%M%S'),
        user=user,
        total_sale=total,
        sub_total=sub_total,       
        tax_total=tax_total,
        deposit_total=deposit_total,
        payment_type=payment_type,
        receipt=receipt,
        products=json.dumps(cart_df.to_dict('records')),
    )