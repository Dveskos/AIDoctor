from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path="crypt.env")  # Φόρτωσε τις μεταβλητές από το .env

apikey = os.getenv("API_KEY")
def question(question):
    client = OpenAI(api_key=apikey, base_url="https://api.perplexity.ai")
    response = client.chat.completions.create(
    model="sonar-pro",
    messages=[
    {"role": "system", "content": "Είσαι βοηθός υγείας." "Αν η παρακάτω ερώτηση δεν περιγράφει συμπτώματα ή ιατρικό πρόβλημα, "
        "απάντησε μόνο: 'Παρακαλώ περιγράψτε τα συμπτώματά σας για να σας βοηθήσω.' "
        "Αν περιέχει συμπτώματα, απάντησε κανονικά στη γλώσσα της ερώτησης."},
    {"role": "user", "content": question}
    ]
    )
    return response.choices[0].message.content