from flask import (
    Flask,
    render_template,
    request,
    flash,
    redirect,
    session,
    send_file,
    url_for,
)
import paypalrestsdk  # Import PayPal SDK

import csv
import qrcode
import os

app = Flask(__name__)
app.secret_key = "your_secret_key_here"

my_booking = []


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        email = request.form["email"]
        profile_photo = request.files.get(
            "profile_photo"
        )  # Handle profile photo upload
        if profile_photo:
            profile_photo_path = os.path.join(
                "static/profile_photos", profile_photo.filename
            )
            profile_photo.save(profile_photo_path)  # Save the profile photo

        # Check if the username already exists
        with open("users.csv", "r") as file:
            reader = csv.reader(file)
            for row in reader:
                if row[0] == username:  # Assuming username is in the first column
                    flash("Username already exists. Please choose a different one.")
                    return redirect("/register")

        # Store the new user data, including profile photo if provided
        with open("users.csv", "a", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    username,
                    password,
                    email,
                    profile_photo_path if profile_photo else None,
                ]
            )  # Store username, password, email, and profile photo path

        flash("Registration successful!")
        return redirect("/login")
    return render_template("register.html")


from datetime import datetime  # Add this import at the top of the file


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        # Fetch user data from users.csv
        with open("users.csv", "r") as file:
            reader = csv.reader(file)
            users = list(reader)  # Read all users into a list
            for index, row in enumerate(users):
                if (
                    row[0] == username and row[1] == password
                ):  # Assuming username is in the first column and password in the second
                    session["user"] = username
                    session["email"] = row[2]  # Assuming email is in the third column
                    session["profile_photo"] = (
                        row[3] if len(row) > 3 else None
                    )  # Handle missing profile photo path
                    session["user_logged_in"] = True
                    flash("Login successful!")

                    # Update last_login timestamp
                    users[index][4] = datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )  # Update last_login column

                    # Write updated user data back to users.csv
                    with open("users.csv", "w", newline="") as write_file:
                        writer = csv.writer(write_file)
                        writer.writerows(users)  # Write all users back to the CSV

                    return redirect("/user_dashboard")
        flash("Invalid username or password.")
        return redirect("/login")
    return render_template("login.html")


@app.route("/manage_users")
def manage_users():
    users = []
    try:
        with open("users.csv", "r") as file:
            reader = csv.reader(file)
            next(reader)  # Skip the header row
            for row in reader:
                users.append(
                    row
                )  # Assuming each row contains user data including last login status

    except FileNotFoundError:
        flash("Users file not found.")
    except Exception as e:
        flash(f"An error occurred: {e}")

    return render_template("manage_users.html", users=users)


@app.route("/generate_reports", methods=["GET", "POST"])
def generate_reports():
    return render_template("generate_reports.html")


@app.route("/generate_bookings_report", methods=["POST"])
def generate_bookings_report():
    # Logic to generate bookings report
    flash("Bookings report generated successfully!")
    return redirect("/generate_reports")


@app.route("/generate_users_report", methods=["POST"])
def generate_users_report():
    # Logic to generate users report
    flash("Users report generated successfully!")
    return redirect("/generate_reports")


@app.route("/admin_dashboard", methods=["GET", "POST"])
def admin_dashboard():
    if request.method == "POST":
        password = request.form.get("password")
        if password == "password":  # Replace with your actual secret password
            return render_template("admin_dashboard.html")
        else:
            flash("Invalid password. Access denied.")
            return redirect("/")
    return render_template("admin_dashboard.html", password_required=True)


@app.route("/user_dashboard")
def user_dashboard():
    return render_template(
        "user_dashboard.html",
        user=session["user"],
        profile_photo=session.get("profile_photo"),
    )


@app.route("/add_booking", methods=["GET", "POST"])
def add_booking():
    if request.method == "POST":
        bus_stop = request.form["busStop"]
        destination = request.form["destination"]
        ticket_type = request.form["ticketType"]
        quantity = request.form["quantity"]
        return render_template(
            "add_booking.html",
            bus_stop=bus_stop,
            destination=destination,
            ticket_type=ticket_type,
            quantity=quantity,
        )
    return render_template("add_booking.html")


@app.route("/process_payment", methods=["POST"])
def process_payment():
    bus_stop = request.form.get("busStop")
    destination = request.form.get("destination")
    ticket_type = request.form.get("ticketType")
    quantity = request.form.get("quantity")
    if not os.path.exists("static/qr_codes"):
        os.makedirs("static/qr_codes")  # Create the directory if it doesn't exist
    session["bus_stop"] = bus_stop

    session["destination"] = destination
    session["ticket_type"] = ticket_type
    session["quantity"] = quantity

    price = 0
    if ticket_type == "Business":
        price = 100 * int(quantity)
    elif ticket_type == "Economy":
        price = 50 * int(quantity)
    elif ticket_type == "Premium":
        price = 200 * int(quantity)

    session["total"] = price

    return render_template(
        "payment.html",
        bus_stop=bus_stop,
        destination=destination,
        ticket_type=ticket_type,
        quantity=quantity,
        total=price,
    )


@app.route("/confirm_payment", methods=["POST"])
def display_ticket():
    print(f"Request method: {request.method}")  # Log the request method
    if request.method == "POST":
        bus_stop = request.form.get("busStop") or session.get("bus_stop")
        destination = request.form.get("destination") or session.get("destination")
        ticket_type = request.form.get("ticketType") or session.get("ticket_type")
        quantity = request.form.get("quantity") or session.get("quantity")
        total = request.form.get("total") or session.get("total")
        payment_method = request.form.get("paymentMethod")  # Capture payment method
        user = session["user"]

        # Generate QR code data
        qr_data = f"Bus Stop: {bus_stop}, Destination: {destination}, Ticket Type: {ticket_type}, Quantity: {quantity}"

        # Determine the booking index
        existing_files = os.listdir("static/qr_codes")
        booking_index = len(
            [
                f
                for f in existing_files
                if f.startswith("booking_") and f.endswith(".png")
            ]
        )  # Count existing bookings

        qr_code_path = (
            f"static/qr_codes/booking_{booking_index + 1}.png"  # Name the QR code file
        )

        # Create and save the QR code
        qr_code_img = qrcode.make(qr_data)
        qr_code_img.save(qr_code_path)

        # Generate a unique booking ID
        booking_id = (
            len(open("bookings.csv").readlines()) + 1
        )  # Simple incrementing ID based on existing lines

        # Append booking details to bookings.csv
        with open("bookings.csv", "a", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(
                [booking_id, bus_stop, destination, ticket_type, quantity, total, user]
            )

        # Render the ticket page
        return render_template(
            "ticket.html",
            bus_stop=bus_stop,
            destination=destination,
            ticket_type=ticket_type,
            quantity=quantity,
            total=total,
            qr_code_path=qr_code_path,
        )


@app.route("/cancel_booking", methods=["POST"])
def cancel_booking():
    booking_id = request.form.get("booking_id")
    bookings = []

    # Read existing bookings
    with open("bookings.csv", "r") as file:
        reader = csv.reader(file)
        for row in reader:
            if row[0] != booking_id:  # Keep all bookings except the one to cancel
                bookings.append(row)
            else:
                # Delete the associated QR code file
                qr_code_path = f"static/qr_codes/booking_{booking_id}.png"
                if os.path.exists(qr_code_path):
                    os.remove(qr_code_path)  # Remove the QR code file

    # Write updated bookings back to the CSV
    with open("bookings.csv", "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerows(bookings)

    flash("Booking canceled successfully.")
    return redirect("/view_bookings")


@app.route("/view_bookings")
def view_bookings():
    bookings = []
    try:
        with open("bookings.csv", "r") as file:
            reader = csv.reader(file)
            for row in reader:
                bookings.append(row)
    except FileNotFoundError:
        flash("Bookings file not found.")
    except Exception as e:
        flash(f"An error occurred: {e}")

    return render_template("view_bookings.html", bookings=bookings)


@app.route("/generate_qr", methods=["POST"])
def generate_qr():
    upi_id = request.form.get("upi_id")
    qr_code_img = qrcode.make(upi_id)
    qr_code_path = f"static/qr_codes/{upi_id}.png"
    qr_code_img.save(qr_code_path)
    return send_file(qr_code_path, mimetype="image/png")


@app.route("/delete_user", methods=["POST"])
def delete_user():
    username = request.form.get("username")
    users = []

    # Read existing users
    with open("users.csv", "r") as file:
        reader = csv.reader(file)
        for row in reader:
            if row[0] != username:  # Keep all users except the one to delete
                users.append(row)
            else:
                # Delete the associated QR code file
                qr_code_path = f"static/qr_codes/booking_{booking_id}.png"
                if os.path.exists(qr_code_path):
                    os.remove(qr_code_path)  # Remove the QR code file

    # Write updated users back to the CSV
    with open("users.csv", "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerows(users)

    flash(f"User '{username}' has been deleted successfully.")
    return redirect("/admin_dashboard")


@app.route("/logout")
def logout():
    session.pop("user_logged_in", None)
    session.pop("user", None)
    session.pop("email", None)
    session.pop("profile_photo", None)  # Clear profile photo from session
    flash("You have been logged out.")
    return redirect("/")


@app.route("/update_profile", methods=["POST"])
def update_profile():
    username = request.form["username"]
    email = request.form["email"]
    profile_photo = request.files.get("profile_photo")

    # Create the directory if it doesn't exist
    if not os.path.exists("static/profile_photos"):
        os.makedirs("static/profile_photos")

    if profile_photo:
        profile_photo_path = os.path.join(
            "static/profile_photos", profile_photo.filename
        )
        profile_photo.save(profile_photo_path)
        session["profile_photo"] = (
            profile_photo_path  # Store the photo path in the session
        )

    session["user"] = username
    session["email"] = email
    flash("Profile updated successfully!")

    # Update user data in users.csv
    users = []
    with open("users.csv", "r") as file:
        reader = csv.reader(file)
        for row in reader:
            if row[0] == username:  # Check if the username matches
                row[2] = email  # Update email
                row[3] = profile_photo_path  # Update profile photo path
            users.append(row)

    with open("users.csv", "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerows(users)  # Write updated user data back to the CSV

    return redirect("/profile_settings")


@app.route("/profile_settings")
def profile_settings():
    bookings = []
    total_spent = 0
    try:
        with open("bookings.csv", "r") as file:
            reader = csv.reader(file)
            for row in reader:
                bookings.append(row)
                total_spent += float(row[5])  # Assuming total is in the 6th column
    except FileNotFoundError:
        flash("Bookings file not found.")
    except Exception as e:
        flash(f"An error occurred: {e}")

    return render_template(
        "profile_settings.html",
        bookings=bookings,
        total_spent=total_spent,
        profile_photo=session.get("profile_photo"),
    )


@app.route("/delete_account", methods=["POST"])
def delete_account():
    username = session.get("user")
    if username:
        # Read existing users
        users = []
        with open("users.csv", "r") as file:
            reader = csv.reader(file)
            for row in reader:
                if row[0] != username:  # Keep all users except the one to delete
                    users.append(row)

        # Write updated users back to the CSV
        with open("users.csv", "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerows(users)

        # Delete user's bookings and associated QR codes
        bookings = []
        with open("bookings.csv", "r") as file:
            reader = csv.reader(file)
            for row in reader:
                if (
                    len(row) > 6 and row[6] != username
                ):  # Keep all bookings except those of the deleted user
                    bookings.append(row)
                else:
                    # Delete the associated QR code file
                    booking_id = row[0]  # Assuming booking ID is in the first column
                    qr_code_path = f"static/qr_codes/booking_{booking_id}.png"
                    if os.path.exists(qr_code_path):
                        os.remove(qr_code_path)  # Remove the QR code file

        # Write updated bookings back to the CSV
        with open("bookings.csv", "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerows(
                bookings
            )  # Write only the bookings that are not associated with the deleted user

        # Delete the user's profile photo if it exists
        profile_photo_path = session.get("profile_photo")
        if profile_photo_path and os.path.exists(profile_photo_path):
            os.remove(profile_photo_path)  # Remove the profile photo file

        bookings = []
        with open("bookings.csv", "r") as file:
            reader = csv.reader(file)
            for row in reader:
                if (
                    row[1] != username
                ):  # Keep all bookings except those of the deleted user
                    bookings.append(row)

        # Write updated bookings back to the CSV
        with open("bookings.csv", "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerows(bookings)

        # Clear session data
        session.clear()
        flash("Your account and associated bookings have been deleted successfully.")
    else:
        flash("No user is logged in.")
    return redirect("/")


@app.route("/contact_us")
def contact_us():
    if request.method == "POST":
        # Logic to handle contact form submission goes here
        flash("Your message has been sent successfully!")
        return redirect("/user_dashboard")
    return render_template("contact_us.html")


@app.route("/learn_more")
def learn_more():
    return render_template("learn_more.html")


@app.route("/designer_contact")
def help_support():
    return render_template("help_support.html")


@app.route("/change_password", methods=["GET", "POST"])
def change_password():
    if request.method == "POST":
        current_password = request.form["current_password"]
        new_password = request.form["new_password"]

        # Fetch user data from users.csv
        username = session.get("user")
        if username:
            with open("users.csv", "r") as file:
                reader = csv.reader(file)
                for row in reader:
                    if (
                        row[0] == username and row[1] == current_password
                    ):  # Check current password
                        row[1] = new_password  # Update password
                        # Write updated user data back to the CSV
                        users = []
                        with open("users.csv", "r") as read_file:
                            read_reader = csv.reader(read_file)
                            for read_row in read_reader:
                                if read_row[0] == username:
                                    read_row[1] = new_password  # Update password
                                users.append(read_row)

                        with open("users.csv", "w", newline="") as write_file:
                            writer = csv.writer(write_file)
                            writer.writerows(
                                users
                            )  # Write updated user data back to the CSV

                        flash("Password changed successfully!")
                        return redirect("/profile_settings")
        flash("Current password is incorrect.")
        return redirect("/change_password")
    return render_template("change_password.html")


if __name__ == "__main__":
    app.run(debug=True)
