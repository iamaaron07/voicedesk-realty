"""Create or promote a staff account from a trusted local operator shell."""
import argparse, getpass
from sqlalchemy import select
from app import SessionLocal, User, hash_password

parser=argparse.ArgumentParser()
parser.add_argument("email")
parser.add_argument("--role",choices=["customer","agent","admin"],required=True)
args=parser.parse_args()
password=getpass.getpass("Account password (minimum 10 characters): ")
if len(password)<10 or not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password): raise SystemExit("Password must be at least 10 characters and include a letter and a number.")
email=args.email.strip().lower()
with SessionLocal() as db:
    user=db.scalar(select(User).where(User.email==email))
    if user:
        user.role=args.role;user.password_hash=hash_password(password)
    else:
        user=User(email=email,password_hash=hash_password(password),role=args.role);db.add(user)
    db.commit()
print(f"Account provisioned with role '{args.role}'.")
