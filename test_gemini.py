from google import genai
import os

# Assicurati di aver impostato GOOGLE_API_KEY in ambiente:
# export GOOGLE_API_KEY="la_tua_chiave"
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
# Per semplice test chat:
chat = client.chats.create(model="gemini-2.0-flash")  # o modello disponibile
response = chat.send_message("Ciao, come stai?")
print("Risposta Gemini:", response.text)
