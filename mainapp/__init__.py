import os


def confirm_client_secret():
    """
    Makes sure client_secret.json is placed in project directory
    If not, assuming it is on Heroku or github actions. Loads data from
    $GOOGLE_API_SECRET
    """

    if not os.path.exists("client_secret.json"):
        if os.getenv("GOOGLE_API_SECRET") == None:
            print("WARNING: Enter client_secret.json to directory")
            exit(-1)
        with open("client_secret.json", "w") as f:
            f.write(os.getenv("GOOGLE_API_SECRET"))


confirm_client_secret()

from . import services

services.initialize_services()
