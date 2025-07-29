# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import pickle

# Load your trained objects (make sure they are saved using pickle)
from original import SupportChatbot  # your SupportChatbot class

# Load models
main_model = pickle.load(open("main_model.pkl", "rb"))
sub_model = pickle.load(open("sub_model.pkl", "rb"))
tfidf = pickle.load(open("tfidf.pkl", "rb"))
ohe = pickle.load(open("ohe.pkl", "rb"))
df = pickle.load(open("df.pkl", "rb"))

bot = SupportChatbot(main_model, sub_model, tfidf, ohe, df)

app = Flask(__name__)
CORS(app)  # allow frontend requests

@app.route('/api/predict', methods=['POST'])
def predict():
    data = request.get_json()
    message = data.get("message", "")
    bot_reply = bot.handle_user(message)
    return jsonify({"reply": bot_reply})


@app.route("/", methods=["GET"])
def home():
    return "Chatbot API is running!"


if __name__ == "__main__":
    app.run(debug=True)
