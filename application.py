import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    details = db.execute("SELECT * FROM purchases WHERE user = :user",user = session["user_id"])
    cash = db.execute("SELECT cash from users WHERE id = :user",user = session["user_id"])
    cash = cash[0]["cash"]
    total = 0
    for detail in details:
        total+=detail["TOTAL"]
    return render_template("index.html",details = details,cash=cash,total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():

    if request.method == "POST":
        # Ensure username was submitted
        quantity = int(request.form.get("shares"))
        if not request.form.get("symbol"):
            return apology("must provide symbol", 403)

        # Ensure password was submitted
        elif quantity < 0:
            return apology("must provide password", 403)

        stock = request.form.get("symbol")
        quote = lookup(stock)
        price = quote["price"]
        user = session["user_id"]
        money = db.execute("SELECT * FROM users WHERE id = :userid", userid=session["user_id"])
        amt = float(money[0]['cash'])
        total = round(price * quantity,2)

        if amt < total:
            return apology("not have enough money", 403)
        else:
            final = amt - total
            db.execute("UPDATE users SET cash = :cash WHERE id = :userid",cash = final,userid=session["user_id"])
            db.execute("INSERT INTO purchases (user,stock,quantity,price,name,TOTAL) VALUES (:user,:stock,:quant,:price,:name,:total)",user = session["user_id"],stock = quote["symbol"],quant = quantity,price = price,name = quote["name"],total = total)
            db.execute("INSERT INTO history (symbol,price,shares) VALUES (:symbol,:price,:shares)",symbol = quote["symbol"],price = price,shares=quantity )
            return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")





@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    details = db.execute("SELECT * FROM history")
    return render_template("history.html",details=details)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("must provide quote", 403)

        stock  = request.form.get("symbol")


        symbol = lookup(stock)
        return render_template("quoted.html",symbol = symbol)
    else:
        return render_template("quote.html")





@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        elif not request.form.get("password") == request.form.get("confirmation"):
            return apology("password not match", 403)

        user = request.form.get("username")
        pwd = request.form.get("password")
        hash = generate_password_hash(pwd)
        db.execute("INSERT INTO users (username,hash) VALUES (:username,:hash)",username = user,hash=hash)
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        avl = list()
        present_symbol = db.execute("SELECT DISTINCT stock from purchases")
        for sym in present_symbol:
            avl.append(sym["stock"])
        if not request.form.get("symbol"):
            return apology("must provide username", 403)
        elif request.form.get("symbol") not in avl:
            return apology("must provide username", 403)
        shares = int(request.form.get("shares"))
        quantity = -1*shares
        symbol = request.form.get("symbol")
        quote = lookup(symbol)
        price = quote["price"]

        stock = db.execute("SELECT * from purchases where stock = :stock",stock = symbol)
        total = round(stock[0]["TOTAL"],2) - round((shares*price),2)
        left = round(stock[0]["quantity"],2) - shares
        if (shares > stock[0]["quantity"]) or (shares < 0):
            return apology("must provide username", 403)
        else:
            db.execute("UPDATE purchases SET quantity = :quantity , price=:price,TOTAL=:total WHERE stock = :stock",quantity = left,price = price,total=total,stock = symbol)
            cash = db.execute("SELECT cash FROM users where id = :id",id = session["user_id"])
            cash = (cash[0]["cash"]) + round((shares*price),2)
            db.execute("UPDATE users SET cash = :cash WHERE id = :id",cash=cash,id= session["user_id"])
            db.execute("INSERT INTO history (symbol,price,shares) VALUES (:symbol,:price,:shares)",symbol = quote["symbol"],price = price,shares=quantity )
            return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        details = db.execute("SELECT * FROM purchases")
        return render_template("sell.html",details = details)



def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
