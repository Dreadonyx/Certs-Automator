from flask import Flask, render_template, request, send_file, jsonify
from PIL import Image, ImageDraw, ImageFont
import io
import base64
import os
import csv
import zipfile
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'

os.makedirs('uploads', exist_ok=True)

# Font mapping for Linux system fonts
FONT_MAP = {
    'arial.ttf': '/usr/share/fonts/noto/NotoSans-Regular.ttf',
    'georgia.ttf': '/usr/share/fonts/noto/NotoSerif-Regular.ttf',
    'times.ttf': '/usr/share/fonts/noto/NotoSerif-Regular.ttf',
}

# Supported MIME types → (PIL format, file extension)
IMAGE_FORMATS = {
    'image/png':  ('PNG',  'png'),
    'image/jpeg': ('JPEG', 'jpg'),
    'image/jpg':  ('JPEG', 'jpg'),
    'image/webp': ('WEBP', 'webp'),
    'image/bmp':  ('BMP',  'bmp'),
    'image/tiff': ('TIFF', 'tiff'),
    'image/gif':  ('GIF',  'gif'),
}


def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def load_font(font_family, size):
    font_path = FONT_MAP.get(font_family, font_family)
    try:
        return ImageFont.truetype(font_path, size)
    except OSError:
        try:
            return ImageFont.truetype('/usr/share/fonts/noto/NotoSans-Regular.ttf', size)
        except OSError:
            return ImageFont.load_default(size=size)


def decode_template(template_data):
    """Decode a base64 data-URL. Returns (PIL Image, pil_format, file_extension)."""
    header, raw = template_data.split(',', 1)
    # header looks like: data:image/png;base64
    mime = header.split(':')[1].split(';')[0].lower()
    pil_format, ext = IMAGE_FORMATS.get(mime, ('PNG', 'png'))
    image = Image.open(io.BytesIO(base64.b64decode(raw)))
    # Preserve original mode for JPEG (no alpha), convert others as needed
    if pil_format == 'JPEG' and image.mode in ('RGBA', 'P'):
        image = image.convert('RGB')
    return image, pil_format, ext


def draw_certificate(template_image, name, department, settings):
    """Draw name and department text onto a copy of the template. Returns PIL Image."""
    certificate = template_image.copy()
    draw = ImageDraw.Draw(certificate)

    name_font = load_font(settings.get('nameFont', 'arial.ttf'), int(settings.get('nameFontSize', 38)))
    dept_font = load_font(settings.get('deptFont', 'arial.ttf'), int(settings.get('deptFontSize', 32)))

    draw.text(
        (int(settings.get('nameX', 420)), int(settings.get('nameY', 270))),
        name,
        fill=hex_to_rgb(settings.get('nameColor', '#000000')),
        font=name_font,
    )
    draw.text(
        (int(settings.get('deptX', 76)), int(settings.get('deptY', 303))),
        department,
        fill=hex_to_rgb(settings.get('deptColor', '#000000')),
        font=dept_font,
    )
    return certificate


def image_to_bytes(image, pil_format):
    """Save PIL image to bytes in the given format."""
    img_io = io.BytesIO()
    if pil_format == 'JPEG' and image.mode in ('RGBA', 'P'):
        image = image.convert('RGB')
    image.save(img_io, pil_format)
    img_io.seek(0)
    return img_io.getvalue()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/parse-csv', methods=['POST'])
def parse_csv():
    """Parse CSV file and return participant data."""
    try:
        if 'csvFile' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400

        file = request.files['csvFile']

        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400

        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_reader = csv.reader(stream)

        participants = []
        next(csv_reader, None)  # Skip header row

        for row in csv_reader:
            if len(row) >= 1 and row[0].strip():
                participants.append({
                    'name': row[0].strip(),
                    'department': row[1].strip() if len(row) > 1 else ''
                })

        return jsonify({
            'success': True,
            'participants': participants,
            'count': len(participants)
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/generate', methods=['POST'])
def generate_certificate():
    """Generate a single certificate and return it as a base64 image."""
    try:
        data = request.json
        template_image, pil_format, ext = decode_template(data.get('template'))
        certificate = draw_certificate(
            template_image,
            name=data.get('name', ''),
            department=data.get('department', ''),
            settings=data,
        )

        img_bytes = image_to_bytes(certificate, pil_format)
        mime = f"image/{ext}" if ext != 'jpg' else 'image/jpeg'

        return jsonify({
            'success': True,
            'image': f"data:{mime};base64,{base64.b64encode(img_bytes).decode()}",
            'ext': ext,
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/generate-batch', methods=['POST'])
def generate_batch():
    """Generate certificates for all participants and return a ZIP file."""
    try:
        data = request.json
        template_image, pil_format, ext = decode_template(data.get('template'))
        participants = data.get('participants', [])
        settings = data.get('settings', {})

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for participant in participants:
                certificate = draw_certificate(
                    template_image,
                    name=participant['name'],
                    department=participant.get('department', ''),
                    settings=settings,
                )
                img_bytes = image_to_bytes(certificate, pil_format)
                safe_name = participant['name'].replace(' ', '_')
                zf.writestr(f"{safe_name}_certificate.{ext}", img_bytes)

        zip_buffer.seek(0)
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name='certificates.zip',
        )

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
