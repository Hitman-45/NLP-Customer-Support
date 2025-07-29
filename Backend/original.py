import pandas as pd
import numpy as np
import re
from sklearn.neighbors import NearestNeighbors
from scipy.sparse import hstack
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
import os
from openpyxl import load_workbook
from datetime import datetime

# Preprocessing
stop_words = set(stopwords.words('english'))
lemmatizer = WordNetLemmatizer()

def clean_text(text):
    text = text.lower()
    text = re.sub(r'[^a-z\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    words = text.split()
    words = [lemmatizer.lemmatize(word) for word in words if word not in stop_words]
    return ' '.join(words)

INTENT_SLOTS = {
    "Refund request": ["product_name", "order_id", "reason"],
    "Technical issue": ["product_name", "order_id", "issue_description"],
    "Billing inquiry": ["order_id"],
    "Cancellation request": ["order_id"],
    "Product inquiry": ["product_name", "order_id"],
    "Product inquiry → Warranty": ["product_name", "order_id"],
    "Product inquiry → Availability": ["product_name", "order_id"],
    "Product inquiry → Specification": ["product_name", "order_id"]
}

AUTO_INTENT_KEYWORDS = {
    "Refund request": [
        "return", "refund", "get my money back", "money refund", 
        "wrong product", "want refund", "replace", "replacement"
    ],
    "Technical issue": [
        "not working", "broken", "issue", "problem", "error", 
        "damaged", "malfunction", "doesn't start", "crashed", 
        "stuck", "hang", "overheating", "battery issue"
    ],
    "Billing inquiry": [
        "bill", "payment", "charged", "invoice", "extra charge", 
        "wrong amount", "billing", "double charged", "not received bill"
    ],
    "Cancellation request": [
        "cancel", "cancellation", "stop order", "don’t want", 
        "terminate", "abort order", "hold my order"
    ],
    "Product inquiry": [
        "specification", "specs", "features", "available", 
        "availability", "warranty", "details", "info", 
        "in stock", "how long warranty", "is it available"
    ],
    "Greeting": ["hello", "hi", "hey", "good morning", "good evening", "greetings"]
}


# --------------------------------- Chatbot Class --------------------------------- #
class SupportChatbot:
    def __init__(self, main_model, sub_model, tfidf, ohe, df):
        self.main_model = main_model
        self.sub_model = sub_model
        self.tfidf = tfidf
        self.ohe = ohe
        self.df = df
        self.chat_history = []
        self.session = {}
        self.nn = NearestNeighbors(n_neighbors=3, metric='cosine')
        self.nn.fit(tfidf.transform(df['text'].apply(clean_text)))

    def add_message(self, role, message):
        self.chat_history.append({"role": role, "message": message})

    def predict_intent(self, text, meta):
        cleaned = clean_text(text)
        vec_text = self.tfidf.transform([cleaned])
        meta_df = pd.DataFrame([meta], columns=['product_category', 'ticket_hour'])
        vec_meta = self.ohe.transform(meta_df)
        vec_combined = hstack([vec_text, vec_meta])

        probs = self.main_model.predict_proba(vec_combined)
        confidence = probs.max()
        label = self.main_model.classes_[probs.argmax()]

        if label == 'Product inquiry':
            sub_label = self.sub_model.predict(vec_text)[0]
            return f"{label} → {sub_label}", confidence

        return label, confidence

    def fallback_intent(self, text):
        text_lower = text.lower()
        for intent, keywords in AUTO_INTENT_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                return intent
        return None

    def extract_slots(self, intent, text):
        slots_required = INTENT_SLOTS.get(intent, []) or INTENT_SLOTS.get(intent.split(" → ")[0], [])
        extracted = {}
        text_lower = text.lower()

        # Extract product_name using known keywords
        if "product_name" in slots_required:
            product_keywords = ['tv', 'laptop', 'fan', 'shirt', 'book', 'phone', 'headphones', 'router']
            for word in product_keywords:
                if word in text_lower:
                    extracted["product_name"] = word
                    break

        # Extract order_id
        if "order_id" in slots_required:
            match = re.search(r'\b\d{6,}\b', text_lower)
            if match:
                extracted["order_id"] = match.group()

        # Extract reason or issue_description
        if "reason" in slots_required or "issue_description" in slots_required:
            keywords = ["not working", "broken", "damaged", "defective", "stopped working"]
            for kw in keywords:
                if kw in text_lower:
                    if "reason" in slots_required:
                        extracted["reason"] = kw
                    if "issue_description" in slots_required:
                        extracted["issue_description"] = kw

        return extracted

    def log_to_excel(self, intent, slots):
        base_intent = intent.split(" → ")[0]
        filename = "support_logs.xlsx"

        # Add timestamp and full intent
        log_entry = slots.copy()
        log_entry["intent"] = intent
        log_entry["timestamp"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        new_entry = pd.DataFrame([log_entry])

        if os.path.exists(filename):
            with pd.ExcelWriter(filename, engine="openpyxl", mode='a', if_sheet_exists='overlay') as writer:
                try:
                    existing_df = pd.read_excel(filename, sheet_name=base_intent)
                    combined = pd.concat([existing_df, new_entry], ignore_index=True)
                    writer.book.remove(writer.book[base_intent])
                    combined.to_excel(writer, sheet_name=base_intent, index=False)
                except:
                    new_entry.to_excel(writer, sheet_name=base_intent, index=False)
        else:
            with pd.ExcelWriter(filename, engine="openpyxl") as writer:
                new_entry.to_excel(writer, sheet_name=base_intent, index=False)

    def handle_user(self, user_input, meta=['Electronics', 12], threshold=0.4):
        self.add_message("user", user_input)

        # Check for greetings before intent prediction
        if self.is_greeting(user_input):
            response = "Hi there! How can I assist you today?"
            self.add_message("bot", response)
            return response

        if 'intent' not in self.session:
            intent, confidence = self.predict_intent(user_input, meta)
            if confidence < threshold:
                fallback = self.fallback_intent(user_input)
                if fallback:
                    intent = fallback
                else:
                    self.add_message("bot", "Sorry, I couldn't understand. Escalating to human support.")
                    return "Escalated"

            self.session = {"intent": intent, "slots": {}, "state": "collecting"}

        intent = self.session['intent']
        extracted = self.extract_slots(intent, user_input)
        self.session['slots'].update(extracted)

        main_intent_key = intent.split(" → ")[0] if "→" in intent else intent
        required_slots = INTENT_SLOTS.get(intent) or INTENT_SLOTS.get(main_intent_key, [])

        missing = [s for s in required_slots if s not in self.session['slots']]
        if missing:
            self.add_message("bot", f"Please provide: {missing[0]}")
        else:
            response = f"Your request for '{intent}' has been submitted with info: {self.session['slots']}"
            self.add_message("bot", response)

            # Log to Excel
            self.log_to_excel(intent, self.session['slots'])

            self.session = {}

        return self.chat_history[-1]['message']

    def is_greeting(self, text):
        text_lower = text.lower()
        greetings = AUTO_INTENT_KEYWORDS.get("Greeting", [])
        return any(greet in text_lower for greet in greetings)

    def get_chat_history(self):
        return self.chat_history
