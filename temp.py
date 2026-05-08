import httpx

headers = {
    "Authorization": "Bearer VENICE_INFERENCE_KEY_459niZyOE-6rwKw79Z6zuyLq68Pg6jj3l2X23",
    "Content-Type": "application/json"
}
data = {
    "model": "venice-uncensored",
    "messages": [{"role": "user", "content": "Hi"}]
}

# Testing the endpoint directly
with httpx.Client() as client:
    response = client.post("https://api.venice.ai/api/v1/chat/completions", headers=headers, json=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    