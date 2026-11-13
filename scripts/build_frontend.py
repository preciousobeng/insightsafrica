"""Required frontend build after checkout/pull, before serving; never deploys.

Both the deployment build command and monthly refresh use the same homepage
builder. Generated assets remain ignored and cannot dirty the Git checkout.
"""

from build_homepage_summary import main

if __name__ == "__main__":
    main()
