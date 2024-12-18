

from flask import Flask, request, jsonify, send_from_directory, redirect, url_for, render_template, session
from flask_sqlalchemy import SQLAlchemy
import openai
import os


app = Flask(__name__, static_folder='static')

# Configure the database URI
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:root%4012@localhost/chatbot_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key'
db = SQLAlchemy(app)

# Set up OpenAI API key securely
openai.api_key = os.getenv("OPENAI_API_KEY")

# Define admin credentials
ADMIN_USERNAME = "Sunil"
ADMIN_PASSWORD = "Sunil"

class Query(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(500), nullable=False)
    answer = db.Column(db.String(1000), nullable=False)

# Serve the main page
@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

# Chat endpoint for handling user messages
@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        print("Incoming Chat Request")

        # Extract JSON data
        data = request.json
        if not data:
            print("Error: No JSON data provided")
            return jsonify({"error": "No data provided"}), 400

        user_message = data.get('message', '').strip()
        if not user_message:
            print("Error: Empty message received")
            return jsonify({"error": "Message cannot be empty"}), 400

        # Check for a matching query in the database
        try:
            similar_query = Query.query.filter(
                db.func.lower(Query.question).contains(user_message.lower())
            ).first()
            if similar_query:
                print(f"Database Match Found: {similar_query.question}")
                return jsonify({
                    "response": similar_query.answer,
                    "source": "database"
                }), 200
        except Exception as db_error:
            print(f"Database Query Error: {db_error}")
            return jsonify({"error": "Database query failed", "details": str(db_error)}), 500

        # OpenAI API Call
        try:
            if not openai.api_key:
                print("Error: OpenAI API key not set")
                return jsonify({"error": "Server configuration issue"}), 500

            response = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant. Respond concisely."},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=150
            )
            ai_response = response.choices[0].message['content'].strip()
            print(f"AI Response: {ai_response}")

            # Save to the database
            try:
                new_query = Query(question=user_message, answer=ai_response)
                db.session.add(new_query)
                db.session.commit()
                print("Saved new query to database")
            except Exception as db_commit_error:
                print(f"Database Save Error: {db_commit_error}")
                return jsonify({"error": "Unable to save response to database"}), 500

            return jsonify({
                "response": ai_response,
                "source": "AI"
            }), 200

        except openai.error.OpenAIError as ai_error:  # Corrected exception handling
            print(f"OpenAI API Error: {ai_error}")
            return jsonify({"error": "AI service failed", "details": str(ai_error)}), 500

    except Exception as e:
        print(f"Unexpected Error: {e}")
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500













     # Re-raise to be caught in the route handler
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Validate credentials
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['logged_in'] = True  # Store login state in the session
            return redirect(url_for('faq_management'))
        else:
            return render_template('login.html', error="Invalid credentials. Please try again.")
    
    return render_template('login.html')

@app.route('/faq_management')
def faq_management():
    if not session.get('logged_in'):
        return redirect(url_for('login'))  # Redirect to login if not authenticated
    return render_template('faq_management.html')  # Render FAQ management page

@app.route('/logout')
def logout():
    session.pop('logged_in', None)  # Clear the login state from the session
    return redirect(url_for('index'))

@app.route('/api/queries', methods=['GET'])
def get_queries():
    queries = Query.query.all()
    return jsonify([{"id": q.id, "question": q.question, "answer": q.answer} for q in queries])

@app.route('/api/faqs', methods=['GET'])
def get_faqs():
    try:
        faqs = Query.query.order_by(Query.id.desc()).limit(7).all()
        return jsonify([{"question": faq.question, "answer": faq.answer} for faq in faqs])
    except Exception as e:
        return jsonify({"status": "error", "message": "Failed to retrieve FAQs", "details": str(e)}), 500

@app.route('/api/update_faq', methods=['PUT'])
def update_faq():
    if not session.get('logged_in'):
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        faq_id = data.get('id')
        question = data.get('question', '').strip()
        answer = data.get('answer', '').strip()
        
        # Validate input
        if not all([faq_id, question, answer]):
            return jsonify({"error": "Question and answer cannot be empty"}), 400
        
        # Get the FAQ entry
        faq = Query.query.get(faq_id)
        if not faq:
            return jsonify({"error": "FAQ not found"}), 404
        
        # Update the FAQ
        faq.question = question
        faq.answer = answer
        
        # Commit the changes
        db.session.commit()
        
        return jsonify({
            "status": "success",
            "message": "FAQ updated successfully",
            "data": {
                "id": faq.id,
                "question": faq.question,
                "answer": faq.answer
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "error": "Failed to update FAQ",
            "details": str(e)
        }), 500

@app.route('/api/delete_faq/<int:faq_id>', methods=['DELETE'])
def delete_faq(faq_id):
    if not session.get('logged_in'):
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        faq = Query.query.get(faq_id)
        if not faq:
            return jsonify({"error": "FAQ not found"}), 404
        
        db.session.delete(faq)
        db.session.commit()
        
        return jsonify({
            "status": "success",
            "message": "FAQ deleted successfully",
            "data": {"id": faq_id}
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "error": "Failed to delete FAQ",
            "details": str(e)
        }), 500

@app.route('/api/faq/<int:faq_id>', methods=['GET'])
def get_faq(faq_id):
    if not session.get('logged_in'):
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        faq = Query.query.get(faq_id)
        if not faq:
            return jsonify({"error": "FAQ not found"}), 404
        
        return jsonify({
            "status": "success",
            "data": {
                "id": faq.id,
                "question": faq.question,
                "answer": faq.answer
            }
        })
    except Exception as e:
        return jsonify({
            "error": "Failed to retrieve FAQ",
            "details": str(e)
        }), 500

# Catch-all route for undefined paths
@app.route('/<path:path>')
def catch_all(path):
    return jsonify({"error": "Endpoint not found", "path": path}), 404

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)


