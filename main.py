"""Start GR0ND lokaal: voer dit bestand uit (in PyCharm: rechtermuisknop, Run 'main').

De browser opent vanzelf op http://127.0.0.1:8000. Zonder database draait de app in demo-modus,
dus zonder inloggen. Stoppen met Ctrl+C of de rode stopknop.
"""

from gr0nd.app import start_lokaal

if __name__ == "__main__":
    start_lokaal()
