from flask import Flask, request, jsonify, render_template, send_from_directory
import requests
import json
import os
import tempfile
from werkzeug.utils import secure_filename

# For PDF processing
import pypdf

# For DOCX processing
import docx

app = Flask(__name__)

# Configure upload folder
UPLOAD_FOLDER = tempfile.gettempdir()
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limit uploads to 16MB

# Allowed file extensions
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx'}

API_URL = "https://ollama-y2elcua3ga-uc.a.run.app/api/generate"
HEADERS = {"Content-Type": "application/json"}

def allowed_file(filename):
    """Check if the file has an allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(file_path):
    """Extract text from PDF file"""
    text = ""
    try:
        pdf_reader = pypdf.PdfReader(file_path)
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
            print(page.extract_text())
    except Exception as e:
        text = f"Error extracting text from PDF: {str(e)}"
    return text

def extract_text_from_docx(file_path):
    """Extract text from DOCX file"""
    text = ""
    try:
        doc = docx.Document(file_path)
        for para in doc.paragraphs:
            text += para.text + "\n"
            print(para.text)
    except Exception as e:
        text = f"Error extracting text from DOCX: {str(e)}"
    return text

def summarize_text_with_model(text):
    """Summarize text using the LLM API"""
    prompt = f"""
Summarize the following content clearly and concisely in 3-5 sentences:

{text}
"""
    payload = {
        "model": "llama3.2:3b",
        "prompt": prompt
    }

    # Make the API request
    response = requests.post(API_URL, headers=HEADERS, json=payload, stream=True)
    response.raise_for_status()

    # Collect the full response from the API
    full_response = ""
    for line in response.iter_lines(decode_unicode=True):
        if line:
            chunk = json.loads(line)
            full_response += chunk.get("response", "")

    return full_response.strip()


def get_bloom_taxonomy_guidance(bloom_level):
    """Return specific guidance for creating questions at different Bloom's taxonomy levels"""
    bloom_guidance = {
        "Remember": {
            "description": "Focus on recalling facts, terms, basic concepts, or answers without necessarily understanding them.",
            "verbs": ["define", "list", "memorize", "recall", "repeat", "identify", "name", "state", "label", "recognize"],
            "example_stems": [
                "What is the definition of...?",
                "Who discovered...?",
                "When did ___ happen?",
                "List the main components of...",
                "Identify the key features of..."
            ]
        },
        "Understand": {
            "description": "Focus on demonstrating understanding of facts and ideas by organizing, comparing, translating, interpreting, giving descriptions, and stating main ideas.",
            "verbs": ["explain", "describe", "interpret", "summarize", "translate", "classify", "compare", "contrast", "paraphrase"],
            "example_stems": [
                "Explain the concept of...",
                "Summarize the main points of...",
                "How would you compare...?",
                "What is the main idea of...?",
                "Describe in your own words what..."
            ]
        },
        "Apply": {
            "description": "Focus on using acquired knowledge to solve problems in new situations by applying acquired knowledge, facts, techniques and rules.",
            "verbs": ["apply", "use", "implement", "solve", "demonstrate", "compute", "calculate", "illustrate", "show"],
            "example_stems": [
                "How would you use ___ to solve...?",
                "Calculate the result when...",
                "Apply the concept of ___ to...",
                "What would happen if...?",
                "What examples can you find to...?"
            ]
        },
        "Analyze": {
            "description": "Focus on examining and breaking information into parts by identifying motives or causes; making inferences and finding evidence to support generalizations.",
            "verbs": ["analyze", "differentiate", "distinguish", "examine", "categorize", "compare", "contrast", "investigate", "break down"],
            "example_stems": [
                "What are the parts or features of...?",
                "How would you categorize...?",
                "What evidence supports...?",
                "What is the relationship between...?",
                "Analyze why... occurred."
            ]
        },
        "Evaluate": {
            "description": "Focus on presenting and defending opinions by making judgments about information, validity of ideas, or quality of work based on a set of criteria.",
            "verbs": ["evaluate", "judge", "critique", "justify", "defend", "recommend", "prioritize", "rate", "assess", "validate"],
            "example_stems": [
                "What is your opinion of...?",
                "How would you evaluate the effectiveness of...?",
                "Judge the value of... according to...",
                "What criteria would you use to assess...?",
                "How would you prioritize... based on...?"
            ]
        },
        "Create": {
            "description": "Focus on compiling information together in a different way by combining elements in a new pattern or proposing alternative solutions.",
            "verbs": ["create", "design", "develop", "formulate", "construct", "imagine", "propose", "devise", "invent", "compose"],
            "example_stems": [
                "How would you design a new...?",
                "What alternative would you propose for...?",
                "Develop a plan to...",
                "Create a new model that...",
                "How would you compose a ___ that...?"
            ]
        }
    }
    
    return bloom_guidance.get(bloom_level, bloom_guidance["Understand"])

def get_difficulty_guidance(difficulty):
    """Return specific guidance for creating questions at different difficulty levels"""
    difficulty_guidance = {
        "Easy": {
            "description": "Focus on basic recall and simple comprehension. Use straightforward language and obvious connections.",
            "characteristics": [
                "Direct questions with clear answers",
                "Focus on main concepts only",
                "Minimal complexity",
                "Obvious connections between concepts",
                "Uses familiar examples"
            ]
        },
        "Medium": {
            "description": "Focus on deeper understanding and application. Requires some analysis but with clear parameters.",
            "characteristics": [
                "Requires understanding beyond simple recall",
                "May involve multiple concepts",
                "Moderate complexity",
                "Some inference required",
                "May need application to new situations"
            ]
        },
        "Hard": {
            "description": "Focus on complex analysis, synthesis, or evaluation. Requires deeper thinking and connections.",
            "characteristics": [
                "Requires synthesis of multiple concepts",
                "High complexity",
                "Significant critical thinking required",
                "May involve ambiguity or nuance",
                "Requires connections between disparate ideas"
            ]
        }
    }
    
    return difficulty_guidance.get(difficulty, difficulty_guidance["Medium"])

def generate_multiple_choice_questions(summary, quantity, difficulty, bloom_level):
    """Generate multiple choice questions with options and answers"""
    # Get specific guidance for this question type based on Bloom's level and difficulty
    bloom_guidance = get_bloom_taxonomy_guidance(bloom_level)
    difficulty_guidance = get_difficulty_guidance(difficulty)
    
    prompt = f"""
As an expert educator, create {quantity} high-quality multiple-choice questions at the {bloom_level} level of Bloom's taxonomy with {difficulty} difficulty based on this summary:

{summary}

BLOOM'S TAXONOMY LEVEL: {bloom_level}
{bloom_guidance["description"]}
Appropriate verbs to use: {', '.join(bloom_guidance["verbs"][:5])}

DIFFICULTY LEVEL: {difficulty}
{difficulty_guidance["description"]}

STRICT REQUIREMENTS FOR MULTIPLE CHOICE QUESTIONS:
1. Each question MUST truly reflect the {bloom_level} cognitive level
2. For higher cognitive levels, focus on application, comparison, evaluation rather than simple recall
3. Create exactly 4 options per question labeled A, B, C, D
4. ONLY ONE option should be correct
5. All distractors (wrong options) must be plausible
6. Avoid obvious wrong answers or silly distractors
7. For '{difficulty}' difficulty, make options appropriately challenging
8. The options should be distinct from one another (not overlapping)
9. Provide a clear explanation for why the correct answer is right and others are wrong
10. Include a clear justification explaining how the question meets the {bloom_level} level of Bloom's taxonomy

Return JSON in this exact format:
[
  {{
    "question": "The question text",
    "options": ["A. First option", "B. Second option", "C. Third option", "D. Fourth option"],
    "answer": "The letter of the correct option (A, B, C, or D)",
    "explanation": "Explanation of why this answer is correct and others are wrong",
    "bloom_justification": "Explanation of how this question aligns with the {bloom_level} level of Bloom's taxonomy"
  }}
]
Only return valid JSON with NO additional explanations or text.
"""

    response = requests.post(API_URL, headers=HEADERS, json={"model": "llama3.2:3b", "prompt": prompt}, stream=True)
    response.raise_for_status()
    
    full_response = ""
    for line in response.iter_lines(decode_unicode=True):
        if line:
            chunk = json.loads(line)
            full_response += chunk.get("response", "")
    
    try:
        questions = json.loads(full_response)
        return questions
    except json.JSONDecodeError:
        # If there's an issue with parsing, try to extract just the JSON portion
        import re
        json_match = re.search(r'\[\s*{.*}\s*\]', full_response, re.DOTALL)
        if json_match:
            try:
                questions = json.loads(json_match.group(0))
                return questions
            except:
                return [{"question": "Error parsing response", "options": ["A. Error", "B. Error", "C. Error", "D. Error"], "answer": "A", "explanation": "API error", "bloom_justification": "N/A"}]
        return [{"question": "Error generating questions", "options": ["A. Error", "B. Error", "C. Error", "D. Error"], "answer": "A", "explanation": "API error", "bloom_justification": "N/A"}]
def generate_true_false_questions(summary, quantity, difficulty, bloom_level):
    """Generate true/false questions with answers"""
    # Get specific guidance for this question type based on Bloom's level and difficulty
    bloom_guidance = get_bloom_taxonomy_guidance(bloom_level)
    difficulty_guidance = get_difficulty_guidance(difficulty)
    
    prompt = f"""
As an expert educator, create {quantity} high-quality true/false questions at the {bloom_level} level of Bloom's taxonomy with {difficulty} difficulty based on this summary:

{summary}

BLOOM'S TAXONOMY LEVEL: {bloom_level}
{bloom_guidance["description"]}
Appropriate verbs to use: {', '.join(bloom_guidance["verbs"][:5])}

DIFFICULTY LEVEL: {difficulty}
{difficulty_guidance["description"]}

STRICT REQUIREMENTS FOR TRUE/FALSE QUESTIONS:
1. Each question MUST truly reflect the {bloom_level} cognitive level
2. Statements must be fully true or fully false, with no ambiguity
3. Avoid absolutes like "always" or "never" unless truly appropriate
4. For false statements, ensure they're plausibly false (not obviously wrong)
5. For higher cognitive levels, focus on relationships, implications, or applications rather than simple facts
6. Include nuanced statements that require proper understanding, not just memorization
7. For '{difficulty}' difficulty, follow the difficulty guidance provided

Return JSON in this exact format:
[
  {{
    "question": "Statement that is either true or false",
    "answer": "True or False",
    "explanation": "Brief explanation of why this is true or false",
    "bloom_justification": "Brief explanation of how this question meets the {bloom_level} level"
  }}
]
Only return valid JSON with NO additional explanations or text.
"""

    response = requests.post(API_URL, headers=HEADERS, json={"model": "llama3.2:3b", "prompt": prompt}, stream=True)
    response.raise_for_status()
    
    full_response = ""
    for line in response.iter_lines(decode_unicode=True):
        if line:
            chunk = json.loads(line)
            full_response += chunk.get("response", "")
    
    try:
        questions = json.loads(full_response)
        return questions
    except json.JSONDecodeError:
        # If there's an issue with parsing, try to extract just the JSON portion
        import re
        json_match = re.search(r'\[\s*{.*}\s*\]', full_response, re.DOTALL)
        if json_match:
            try:
                questions = json.loads(json_match.group(0))
                return questions
            except:
                return [{"question": "Error parsing response", "answer": "True", "explanation": "API error", "bloom_justification": "N/A"}]
        return [{"question": "Error generating questions", "answer": "True", "explanation": "API error", "bloom_justification": "N/A"}]

def generate_identification_questions(summary, quantity, difficulty, bloom_level):
    """Generate identification/fill-in-the-blank questions with answers"""
    # Get specific guidance for this question type based on Bloom's level and difficulty
    bloom_guidance = get_bloom_taxonomy_guidance(bloom_level)
    difficulty_guidance = get_difficulty_guidance(difficulty)
    
    prompt = f"""
As an expert educator, create {quantity} high-quality identification/fill-in-the-blank questions at the {bloom_level} level of Bloom's taxonomy with {difficulty} difficulty based on this summary:

{summary}

BLOOM'S TAXONOMY LEVEL: {bloom_level}
{bloom_guidance["description"]}
Appropriate verbs to use: {', '.join(bloom_guidance["verbs"][:5])}

DIFFICULTY LEVEL: {difficulty}
{difficulty_guidance["description"]}

STRICT REQUIREMENTS FOR IDENTIFICATION QUESTIONS:
1. Each question MUST truly reflect the {bloom_level} cognitive level
2. The blank or identification must be central to understanding the concept
3. For "Remember" level: Focus on key terms, definitions, or specific facts
4. For "Understand" level: Focus on explaining relationships or meanings
5. For "Apply" level: Focus on using concepts in specific contexts
6. For "Analyze" level: Focus on breaking down components or relationships
7. For "Evaluate" level: Focus on making judgments based on criteria
8. For "Create" level: Focus on generating new ideas or perspectives
9. For '{difficulty}' difficulty, make questions progressively more complex as specified

Return JSON in this exact format:
[
  {{
    "question": "Question asking to identify a term, concept, or fill in a blank",
    "answer": "The correct answer",
    "explanation": "Brief explanation of why this answer is correct",
    "bloom_justification": "Brief explanation of how this question meets the {bloom_level} level"
  }}
]
Only return valid JSON with NO additional explanations or text.
"""

    response = requests.post(API_URL, headers=HEADERS, json={"model": "llama3.2:3b", "prompt": prompt}, stream=True)
    response.raise_for_status()
    
    full_response = ""
    for line in response.iter_lines(decode_unicode=True):
        if line:
            chunk = json.loads(line)
            full_response += chunk.get("response", "")
    
    try:
        questions = json.loads(full_response)
        return questions
    except json.JSONDecodeError:
        # If there's an issue with parsing, try to extract just the JSON portion
        import re
        json_match = re.search(r'\[\s*{.*}\s*\]', full_response, re.DOTALL)
        if json_match:
            try:
                questions = json.loads(json_match.group(0))
                return questions
            except:
                return [{"question": "Error parsing response", "answer": "Error", "explanation": "API error", "bloom_justification": "N/A"}]
        return [{"question": "Error generating questions", "answer": "Error", "explanation": "API error", "bloom_justification": "N/A"}]

def generate_open_ended_questions(summary, quantity, difficulty, bloom_level):
    """Generate open-ended questions with sample answers"""
    # Get specific guidance for this question type based on Bloom's level and difficulty
    bloom_guidance = get_bloom_taxonomy_guidance(bloom_level)
    difficulty_guidance = get_difficulty_guidance(difficulty)
    
    prompt = f"""
As an expert educator, create {quantity} high-quality open-ended questions at the {bloom_level} level of Bloom's taxonomy with {difficulty} difficulty based on this summary:

{summary}

BLOOM'S TAXONOMY LEVEL: {bloom_level}
{bloom_guidance["description"]}
Appropriate verbs to use: {', '.join(bloom_guidance["verbs"][:5])}
Example question stems: 
- {bloom_guidance["example_stems"][0]}
- {bloom_guidance["example_stems"][1]}

DIFFICULTY LEVEL: {difficulty}
{difficulty_guidance["description"]}

STRICT REQUIREMENTS FOR OPEN-ENDED QUESTIONS:
1. Each question MUST truly reflect the {bloom_level} cognitive level without exception
2. For "Remember/Understand" levels: Questions should require explanation of concepts in own words
3. For "Apply" level: Questions should ask students to apply concepts to new situations
4. For "Analyze" level: Questions should require breaking down concepts or comparing elements
5. For "Evaluate" level: Questions should require making judgments based on criteria
6. For "Create" level: Questions should require generating new ideas, plans, or perspectives
7. Include challenging prompts appropriate for '{difficulty}' difficulty
8. Use the verbs and stems provided as guidance for the appropriate cognitive level
9. The sample answer should demonstrate the depth expected at this cognitive level
10. Key points must be concrete, assessable elements that would be in a quality answer

Return JSON in this exact format:
[
  {{
    "question": "Open-ended question that requires a detailed response",
    "answer": "Sample or model answer that demonstrates expected depth and quality",
    "key_points": ["Key point 1 that must be included in a quality answer", "Key point 2", "Key point 3"],
    "bloom_justification": "Brief explanation of how this question meets the {bloom_level} level",
    "grading_criteria": "Brief guidance on how to evaluate student responses"
  }}
]
Only return valid JSON with NO additional explanations or text.
"""

    response = requests.post(API_URL, headers=HEADERS, json={"model": "llama3.2:3b", "prompt": prompt}, stream=True)
    response.raise_for_status()
    
    full_response = ""
    for line in response.iter_lines(decode_unicode=True):
        if line:
            chunk = json.loads(line)
            full_response += chunk.get("response", "")
    
    try:
        questions = json.loads(full_response)
        return questions
    except json.JSONDecodeError:
        # If there's an issue with parsing, try to extract just the JSON portion
        import re
        json_match = re.search(r'\[\s*{.*}\s*\]', full_response, re.DOTALL)
        if json_match:
            try:
                questions = json.loads(json_match.group(0))
                return questions
            except:
                return [{"question": "Error parsing response", "answer": "Error", "key_points": ["API error"], "bloom_justification": "N/A", "grading_criteria": "N/A"}]
        return [{"question": "Error generating questions", "answer": "Error", "key_points": ["API error"], "bloom_justification": "N/A", "grading_criteria": "N/A"}]

def exam_generate_questions(summary, question_list):
    """Generate exam questions based on provided summary and question specifications"""
    results = []
    for question in question_list:
        q_type = question['type'].lower()
        bloom_level = question.get('bloom_level', 'Understand')
        difficulty = question.get('difficulty', 'Medium')
        quantity = question.get('quantity', 1)
        
        # Use the appropriate question generation function based on type
        if q_type == "multiple_choice":
            questions = generate_multiple_choice_questions(summary, quantity, difficulty, bloom_level)
        elif q_type == "true_or_false":
            questions = generate_true_false_questions(summary, quantity, difficulty, bloom_level)
        elif q_type == "identification":
            questions = generate_identification_questions(summary, quantity, difficulty, bloom_level)
        elif q_type == "open_ended":
            questions = generate_open_ended_questions(summary, quantity, difficulty, bloom_level)
        else:
            # Fallback for unknown question types
            questions = [{"error": f"Unknown question type: {q_type}"}]
        
        results.append({
            "type": q_type,
            "bloom_level": bloom_level,
            "questions": questions
        })
    
    return results

@app.route('/')
def home():
    """Serve the main page"""
    return render_template('index.html')

@app.route("/summarize", methods=["POST"])
def summarize_file():
    """Route to summarize uploaded file (txt, pdf, or docx)"""
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded."}), 400

    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No file selected."}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": f"File type not supported. Please upload a txt, pdf, or docx file."}), 400
    
    try:
        # Save the file temporarily
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Extract text based on file type
        file_extension = filename.rsplit('.', 1)[1].lower()
        if file_extension == 'pdf':
            text = extract_text_from_pdf(file_path)
        elif file_extension == 'docx':
            text = extract_text_from_docx(file_path)
        else:  # txt files
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
        
        # Clean up the temporary file
        os.remove(file_path)
        
        if not text or len(text.strip()) < 10:
            return jsonify({"error": "Could not extract sufficient text from the file."}), 400
            
        # Generate summary
        summary = summarize_text_with_model(text)
        return jsonify({"summary": summary, "fileType": file_extension})
    
    except Exception as e:
        return jsonify({"error": f"Error processing file: {str(e)}"}), 500

@app.route("/generate", methods=["POST"])
def generate_questions():
    """Route to generate questions based on summary"""
    data = request.get_json()

    required_fields = ["summary", "questions"]
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields: 'summary' and 'questions'"}), 400

    summary = data['summary']
    questions = data['questions']

    try:
        results = exam_generate_questions(summary, questions)
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/static/<path:path>')
def send_static(path):
    """Serve static files"""
    return send_from_directory('static', path)

if __name__ == "__main__":
    # Get port from environment variable or default to 10000
    port = int(os.environ.get("PORT", 10000))
    
    # Run the app binding to 0.0.0.0 (all network interfaces)
    app.run(host="0.0.0.0", port=port)
    # Ensure the static directory exists
    if not os.path.exists('static'):
        os.makedirs('static')
        
    app.run(debug=True)

