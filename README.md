# Certificate Generator - Flask App

A Flask-based web application to automatically generate certificates with participant names and departments.

## 📁 Project Structure

```
certificate-generator/
│
├── app.py                  # Main Flask application
├── requirements.txt        # Python dependencies
│
├── static/
│   └── style.css          # CSS with :root variables
│
├── templates/
│   └── index.html         # Main HTML template
│
└── uploads/               # Folder for temporary files (auto-created)
```

## 🚀 Setup Instructions

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

Or install individually:
```bash
pip install Flask Pillow Werkzeug
```

### 2. Run the Application

```bash
python app.py
```

The app will start on `http://localhost:5000`

## 💻 Usage

1. **Open your browser** and go to `http://localhost:5000`

2. **Upload certificate template** (cert.png)

3. **Add participant data** in this format:
   ```
   John Doe, Computer Science
   Jane Smith, ECE
   Robert Kumar, AI & DS
   ```

4. **Adjust text positioning** using the controls

5. **Preview** the first certificate to check positioning

6. **Generate all certificates** - they'll download automatically

## 🎨 Customization

All design variables are in `static/style.css` using CSS `:root`:

```css
:root {
    --primary-color: #667eea;
    --primary-dark: #764ba2;
    --spacing-lg: 20px;
    /* ... and more */
}
```

Change these to customize colors, spacing, fonts, etc.

## 📝 Features

- ✅ Upload custom certificate templates
- ✅ Bulk generation from participant list
- ✅ Adjustable text position, size, font, and color
- ✅ Live preview before batch generation
- ✅ Automatic download of all certificates
- ✅ Clean, responsive UI

## 🔧 API Endpoints

### POST /generate
Generate a single certificate
```json
{
  "template": "base64_image_data",
  "name": "John Doe",
  "department": "Computer Science",
  "nameX": 420,
  "nameY": 525,
  ...
}
```

### POST /generate-batch
Generate multiple certificates (currently not used in frontend)

## 🛠️ Troubleshooting

**Fonts not working?**
- The app tries to use system fonts (arial.ttf, georgia.ttf)
- On Windows: Usually works by default
- On Linux/Mac: Install Microsoft fonts or update font paths in `app.py`

**Port already in use?**
Change the port in `app.py`:
```python
app.run(debug=True, host='0.0.0.0', port=8000)
```

## 📦 Deployment

For production, use a WSGI server like Gunicorn:

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## 🎯 Made for

AKIRA CTF - Velammal Engineering College
CYVENTURA - Department of CSE (Cyber Security)
