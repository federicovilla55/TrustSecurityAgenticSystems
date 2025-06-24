import sys
import time
import requests

BASE_URL = "http://localhost:8000/api"
POLL_INTERVAL = 2
TARGET_USERNAME = "Federico"

USERS = [
    {
        "username": "Alice",
        "password": "password",
        "setup_payload": {
            "user": "Alice",
            "content": "I'm Alice, I am a Computer Science student at EPFL with a strong interest in cryptography and information security. I'm looking to connect with fellow students from Swiss universities who are passionate about cryptography, cybersecurity, or related areas. Outside of academics, I enjoy hiking in the Swiss Alps and doing CTF challenges",
            "default_value": 1
        }
    },
    {
        "username": "Bob",
        "password": "password",
        "setup_payload": {
            "user": "Bob",
            "content": "I am Bob, an EPFL graduate working at a Big Tech company as a software engineer. I enjoy reading about systems, distributed computing, and security. I'm looking to connect with fellow professionals in the tech industry as well as students from Swiss universities who are passionate about software engineering, computer science, or career development.",
            "default_value": 1
        }
    }
]



def register_user(username: str, password: str):
    resp = requests.post(f"{BASE_URL}/register", json={
        "username": username,
        "password": password
    })
    resp.raise_for_status()
    print(f"[+] Registered user {username}")


def get_token(username: str, password: str) -> str:
    resp = requests.post(f"{BASE_URL}/token", data={
        "username": username,
        "password": password
    })
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not token:
        raise RuntimeError(f"No token returned for {username}")
    print(f"[+] Got token for {username}")
    return token


def setup_user(token: str, payload: dict):
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.post(f"{BASE_URL}/setup", json=payload, headers=headers)
    resp.raise_for_status()
    print(f"[+] Setup completed for {payload['user']}")

def wait_for_target_relation(token: str, username: str) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    print(f"[~] Waiting for {username} to receive a pairing with '{TARGET_USERNAME}'...")
    while True:
        resp = requests.get(f"{BASE_URL}/relations", headers=headers)
        resp.raise_for_status()
        relations = resp.json().get("relations", [])
                
        if f"{username},{TARGET_USERNAME}" in relations:
            print(f"[!] {username} now has pairing request with '{TARGET_USERNAME}'.")
            break
        time.sleep(POLL_INTERVAL)


def prompt_decision(user: str) -> bool:
    while True:
        ans = input(f"Accept pairing between {user} and {TARGET_USERNAME}? [Y/N]: ").strip().upper()
        if ans in ("Y", "N"):
            return ans.upper()[0] == "Y"
        print("Please enter Y or N.")


def send_feedback(token: str, receiver: str, decision: bool):
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"receiver": receiver, "feedback": 1 if decision else 0}
    resp = requests.post(f"{BASE_URL}/feedback", json=payload, headers=headers)
    resp.raise_for_status()
    print(f"[+] Feedback ({'accepted' if decision else 'rejected'}) sent for pairing with {receiver}")


def main():
    try:
        tokens = {}
        for u in USERS:
            register_user(u["username"], u["password"])
            tok = get_token(u["username"], u["password"])
            tokens[u["username"]] = tok
            setup_user(tok, u["setup_payload"])

        for u in USERS:
            wait_for_target_relation(tokens[u["username"]], u["username"])

        decision = prompt_decision(f"{u['username']} & {TARGET_USERNAME}")
        for u in USERS:
            send_feedback(tokens[u["username"]], TARGET_USERNAME, decision)

    except requests.HTTPError as e:
        print(f"HTTP error {e.response.status_code}: {e.response.text}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    print("Done.")    


if __name__ == "__main__":
    # clear the console

    print("\033c", end="")
    print("Starting demo configuration script...")

    main()
