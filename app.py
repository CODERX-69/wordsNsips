from datetime import datetime
from random import randint
import re
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import secrets
from functools import wraps
from flask_cors import CORS
from flask_pymongo import PyMongo
from flask_bcrypt import Bcrypt
import pandas as pd
import csv


app = Flask(__name__)
app.config["MONGO_URI"] = "mongodb://localhost:27017/WordsNSips"


mongo = PyMongo(app)
bcrypt = Bcrypt(app)


def is_admin(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            if session['type'] == 'admin':
                return f(*args, **kwargs)
        else:
            flash('Please Login First', 'secondary')
            return redirect(url_for('login'))
    return wrap


# def is_tab(f):
#     @wraps(f)
#     def wrap(*args, **kwargs):
#         if 'logged_in' in session:
#             if session['type'] == 'tab':
#                 return f(*args, **kwargs)
#         else:
#             flash('Please Login First', 'secondary')
#             return redirect(url_for('login'))
#     return wrap


def is_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            flash('Please Login First', 'secondary')
            return redirect(url_for('login'))
    return wrap


@app.route('/')
def index():
    return render_template("index.html")

    ########### FIRST ONE THAT APPERAS ON ROUTE ########################
################ This Checkin is for CUSTOMER Type  USERS########################


@app.route('/checkin', methods=['GET', 'POST'])
def checkin():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        location = request.form['location']
        table = request.form['table']
        quantity = int(request.form['quantity'])
        start_time = request.form['start_time']

        mongo.db.users.insert_one(
            {
                "type": "customer",
                "name": name,
                "phone": phone,
                "location": location,
                "table": table,
                "quantity": quantity,
                "start_time": start_time
            }
        )
        session["name"] = name
        session["phone"] = phone
        session['location'] = location
        session['table'] = table
        session["cart"] = {"products": {}, "cart_total": 0}
        session["quantity"] = quantity
        session["start_time"] = start_time
        session["type"] = "customer"
        session["service_charge"] = 100 * quantity
        # return render_template("menu.html")
        return redirect(url_for('menu'))

    ########################### NORMAL MENU FOR CUSTOMER ##############################


@app.route('/menu', methods=["GET", "POST"])
def menu():
    menu = list(mongo.db.menu.find())
    categories = {}
    categories = set()
    for item in menu:
        categories.add(item['category'])
    print(categories)
    return render_template("menu.html", menu=menu, categories=categories)

######### GIVES recent order History #######################


@app.route('/order_history', methods=["GET", "POST"])
def order_history():
    output = list(mongo.db.orders.find({"status": "CLOSED"}))
    total = 0
    for item in output:
        total += item['total']
    return render_template("order_history.html", output=output, total=total)


@app.route('/table')
def table():
    sheet = list(mongo.db.orders.find({"status": "CLOSED"}))
    df = pd.DataFrame(sheet)
    df.to_csv('data.csv')
    flash("CSV file updates successfuly!", "success")
    return render_template("order_history.html")



@app.route('/checkout_order/<int:order_id>', methods=['GET', 'POST'])
def checkout_order(order_id):
    order = mongo.db.orders.update_one(
        {'order_id': int(order_id)}, {'$set': {'status': "CLOSED"}}, upsert=True)
    output = list(mongo.db.orders.find({"status": "CLOSED"}))
    return render_template("order_history.html", output=output, order=order)

################################# triggered When BLUE CART BUTTON is clicked ################


@app.route('/checkout', methods=["POST", "GET"])
def checkout():
    cart_dict = session["cart"]["products"]
    cart = []
    total = 0
    # orders = list(mongo.db.orders.find_one(
    #     {"type": 'tab', "email": session["email"]}))
    # if orders:
    #     for item in orders["order"]:
    #         print(item)
    #         cart.append({
    #             "product_id": item["product_id"],
    #             "name": item["name"],
    #             "quantity": item["quantity"],
    #             "amount": item["amount"],
    #             "category": item["category"]
    #         })

    # sejal@abc.com:
    # {
    #     "order_id",
    #     "date"
    #     "table"
    # }

    for product_id in cart_dict.keys():
        pro = mongo.db.menu.find_one(
            {"product_id": int(product_id)}, {"_id": 0})
        cart.append({
            "product_id": product_id,
            "name": pro.get("name"),
            "quantity": int(cart_dict[product_id]),
            "amount": int(pro.get("price")) * int(cart_dict[product_id]),
            "category": pro.get("category")
        })
        total = total + (int(pro.get("price")) * int(cart_dict[product_id]))
    return render_template("checkout.html", cart=cart, total=total)


################################ WILL TELL  ORDER PLACED IF SUCCESSFULL ################################
@ app.route('/confirm_order')
def confirm_order():
    cart_dict = session["cart"]["products"]
    cart = []
    total = int(session["service_charge"])
    if int(session["cart"]["cart_total"]) > int(session["service_charge"]):
        total += int(session["cart"]["cart_total"]) - \
            int(session["service_charge"])
    for product_id in cart_dict:
        pro = mongo.db.menu.find_one({"product_id": int(product_id)})
        amount = int(pro.get("price")) * int(cart_dict[product_id])
        if session['type'] == "customer":
            cart.append({
                "product_id": product_id,
                "name": pro.get("name"),
                "quantity": int(cart_dict[product_id]),
                "amount": amount,
                "category": pro.get("category"),
                "entry_fee": session["service_charge"],
                "total":total
            })
        else:
            
            cart.append({
                "product_id": product_id,
                "name": pro.get("name"),
                "quantity": int(cart_dict[product_id]),
                "amount": amount,
                "category": pro.get("category"),
                "date":  session["start_time"],
                "entry_fee": session["service_charge"],
                "total" : total
            })
    order_id = randint(1, 99999)
    # total = int(session["service_charge"])
    # if int(session["cart"]["cart_total"]) > int(session["service_charge"]):
    #     total += int(session["cart"]["cart_total"]) - \
    #         int(session["service_charge"])
    mongo.db.orders.update_one(
        {'order_id': order_id}, {'$set': {'quantity': session["quantity"]}})
    if session["type"] == "customer":
        res = mongo.db.orders.insert_one({
            "name": session["name"],
            "order_id": order_id,
            "order": cart,
            "total": total,
            'location': session["location"],
            "start_time": session["start_time"],
            "status": "OPEN",
            "table": session["table"],
            "type": session["type"]
        })

    elif session["type"] == "tab":
        em = mongo.db.orders.find_one({"email": session["email"]})
        cart_total = 0
        if em:
            mongo.db.orders.update_one({"email": session["email"]}, {
                "$push": {"order": {"$each": cart}}}, upsert =True)
        else:
            res = mongo.db.orders.insert_one({
                "name": session["name"],
                "order_id": order_id,
                "order": cart,
                "total": total,
                "status": "OPEN",
                "type": session["type"],
                "email": session["email"]
            })
            session["cart"]
    session["cart"] = {"products": {}, "cart_total": 0}
    session["service_charge"] = 0
    flash("Order placed", "success")  # successfully placed order
    return redirect(url_for("menu"))


############# FOR ADMIN TO ADD / DELETE MENU ITEMS FOR CUSTOMERS ##############################
@ app.route('/admin/dashboard',  methods=['GET', 'POST'])
@ is_admin
def dashboard():
    orders = list(mongo.db.orders.find({'status': 'OPEN'}))
    return render_template("dashboard.html", orders=orders)

    ############# FOR ADMIN TO ADD / DELETE MENU ITEMS FOR CUSTOMERS ##############################


@ app.route('/manage_menu', methods=['GET', 'POST'])
def manage_menu():
    if request.method == "POST":
        category = request.form.get("category")
        item_name = request.form.get("item_name")
        active_status = bool(request.form.get("active_status"))
        price = int(request.form.get("price"))
        product_id = int(randint(6666, 9999))
        mongo.db.menu.insert_one({
            "active": active_status,
            "name": item_name,
            "category": category,
            "price": price,
            "product_id": product_id
        })
        flash("Product successfully added!", "success")

    menu = mongo.db.menu.find()
    return render_template("manage_menu.html", menu=menu)


################## To  delete Order data from that day after calculating daily collection ################
@ app.route('/delete_orders')
def delete_orders():
    orders = list(mongo.db.orders.find())
    if orders:
        mongo.db.orders.delete_many({"status": "CLOSED"})

    else:
        flash("No orders", "info")
    return redirect(url_for("order_history"))


@ app.route('/manage_tabs')
@ is_logged_in
def manage_tabs():
    orders = list(mongo.db.orders.find({"type": "tab"}))
    return render_template("manage_tabs.html", orders=orders)


# @app.route('/menu', methods=["GET", "POST"])
# def menu():
#     menu = list(mongo.db.menu.find())
#     categories = {}
#     categories = set()
#     for item in menu:
#         categories.add(item['category'])
#     print(categories)
#     return render_template("menu.html", menu=menu, categories=categories)

############ ADMIN LOGOUT #############################
@ app.route('/admin/logout/')
@ is_logged_in
def logout():
    if 'logged_in' in session:
        session.clear()
        flash('Successfully logged out', 'success')
        return redirect(url_for('login'))
    else:
        flash('You are not Logged in', 'secondary')
        return redirect(url_for('login'))


@ app.route('/remove_from_cart/<int:product_id>')
def remove_from_cart(product_id):
    product = mongo.db.menu.find_one({"product_id": int(product_id)})
    price = product["price"]
    session["cart"]["cart_total"] -= (int(price) *
                                      int(session["cart"]["products"][str(product_id)]))
    session["cart"]["products"].pop(str(product_id))
    flash("Item deleted from cart!", "info")
    return redirect(url_for("checkout"))


@ app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        admin = mongo.db.admin.find_one()
        user = mongo.db.users.find_one({"email": email})
        if admin:
            if email == admin["email"] and password == admin["password"]:
                session["logged_in"] = True
                session["email"] = email
                session['type'] = 'admin'
                print('password matched')
                return redirect(url_for('dashboard'))
        if user:
            if email == user["email"] and password == user["password"]:
                session["logged_in"] = True
                session["email"] = email
                session['type'] = 'tab'
                session["name"] = user["name"]
                print('password matched')
                return redirect(url_for('tab_checkin'))

    return render_template("login.html")


@ app.route('/add_product/<string:order_id>')
def add_product(order_id):
    all_order = mongo.db.orders.find_one({"order_id": int(order_id)})
    print(all_order)
    orders = all_order["order"]
    print(all_order)
    pro = {
        "name": "Cigarettes",
        "amount": 20,
        "quantity": 1
    }
    for order in orders:
        if order.get("name") == "Cigarettes":
            order["quantity"] += 1
            order["amount"] += 20
            all_order["total"] += 20

            break
    else:
        orders.append(pro)
        all_order["total"] += 20
    print(orders)
    res = mongo.db.orders.update_one({"order_id": int(order_id)}, {
                                     "$set": {"order": orders, "total": all_order["total"]}})
    flash("Product added successfully", "success")
    return redirect(url_for("dashboard", res=res))


@ app.route("/update_quantity/<int:product_id>/<quantity>")
def update_quantity(product_id, quantity):
    if "cart" in session:
        product_dict = session["cart"]["products"]
        product_dict[str(product_id)] = int(quantity)
        cart_total = 0
        for product_id, quantity in product_dict.items():
            product = mongo.db.menu.find_one({"product_id": int(product_id)})
            price = product["price"]
            cart_total += int(price) * int(quantity)
        session["cart"]["cart_total"] = cart_total
        session["cart"] = {"products": product_dict, "cart_total": cart_total}
        flash("Quantity updated!", "info")
    return redirect(url_for("checkout"))


@ app.route("/delete_menu/<int:product_id>")
def delete_menu(product_id):
    print(id)
    res = mongo.db.menu.remove({"product_id": product_id})
    flash("Deleted successfully", "success")
    return redirect(url_for("manage_menu", res=res))


@ app.route('/delete_order/<int:order_id>')
def delete_order(order_id):
    mongo.db.orders.remove({"order_id": order_id})
    return redirect(url_for("order_history"))


@ app.route('/delete_order_tab/<int:order_id>')
def delete_order_tab(order_id):
    mongo.db.orders.remove({"order_id": order_id})
    return redirect(url_for("manage_tabs"))


@ app.route('/add_member', methods=["GET", "POST"])
def add_member():
    name = request.form.get("name")
    email = request.form.get("email")
    password = request.form.get("password")
    res = mongo.db.users.insert_one({
        "name": name,
        "email": email,
        "password": password,
        "type": "tab"
    })
    flash("Added successfully", "success")
    return redirect(url_for("manage_tabs"))


@ app.route('/add_to_cart/<int:product_id>')
def add_to_cart(product_id):
    print(type(product_id))
    print(product_id)
    item = mongo.db.menu.find_one({"product_id": product_id}, {"_id": 0})
    print(item)
    if "cart" in session:
        product_dict = session["cart"]["products"]
        if product_id in product_dict.keys():
            # add number
            print(type(product_id))
            product_dict[product_id] += 1
        else:
            # add key value
            product_dict[product_id] = 1
        total_price = int(session["cart"]["cart_total"])
        total_price += int(item['price'])
        product_dict = dict(session["cart"]["products"])
        keys_values = product_dict.items()
        pro_dict = {int(key): int(value) for key, value in keys_values}
        print(session)

        session["cart"] = {"products": pro_dict, "cart_total": total_price}

    else:
        session["cart"] = {
            "products": {product_id: 1},
            "cart_total": int(item['price']),
        }
    flash("Added product to cart", "success")
    return redirect(url_for("menu"))


@app.route('/tab_checkin', methods=['GET', 'POST'])
def tab_checkin():
    if request.method == "POST":
        table = request.form['table']
        quantity = int(request.form['quantity'])
        start_time = request.form['start_time']
        mongo.db.users.insert_one({
            "name": session["name"],
            "type": 'tab',
            "table": table,
            "quantity": quantity,
            "start_time": start_time,
            "order_id": randint(1, 99999),
            "email": session["email"]
        })
        results = mongo.db.users.find_one({"type": 'tab'})
        session["id"] = results["name"]
        session['table'] = table
        session["cart"] = {"products": {}, "cart_total": 0}
        session["quantity"] = quantity
        session["start_time"] = start_time
        session["service_charge"] = 100 * quantity
        return redirect(url_for('menu'))
    return render_template("tab_checkin.html")


if __name__ == "__main__":
    app.secret_key = "asdtc"
    app.run(debug=True)
