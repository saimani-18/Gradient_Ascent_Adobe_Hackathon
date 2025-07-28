import pdfplumber
import json
import os
import re
from collections import defaultdict

def extract_outline(pdf_path):
    outline = []
    title = ""
    prev_font_sizes = defaultdict(int)
    
    with pdfplumber.open(pdf_path) as pdf:
        first_page_text = pdf.pages[0].extract_text()
        if first_page_text:
            title = first_page_text.split('\n')[0].strip()
        
        for page_num, page in enumerate(pdf.pages, start=1):
            words = page.extract_words(extra_attrs=["fontname", "size", "bold", "italic"])
            
            if not words:
                continue
                
            # Calculate font size statistics
            font_sizes = [word['size'] for word in words]
            avg_size = sum(font_sizes) / len(font_sizes)
            
            # Group words by lines
            lines = defaultdict(list)
            for word in words:
                lines[round(word['top'])].append(word)
            
            for y_pos, line_words in lines.items():
                line_text = ' '.join([w['text'] for w in line_words])
                is_bold = any(w.get('bold') for w in line_words)
                avg_line_size = sum(w['size'] for w in line_words) / len(line_words)
                
                # Determine heading level
                level = None
                if avg_line_size > avg_size * 1.5 and is_bold:
                    level = "H1"
                elif avg_line_size > avg_size * 1.3 and is_bold:
                    level = "H2"
                elif (avg_line_size > avg_size * 1.1 and is_bold) or is_bold:
                    level = "H3"
                
                if level:
                    # Clean up text (remove page numbers, etc.)
                    clean_text = re.sub(r'\s+', ' ', line_text).strip()
                    clean_text = re.sub(r'^\d+\s*', '', clean_text)
                    
                    outline.append({
                        "level": level,
                        "text": clean_text,
                        "page": page_num
                    })
    
    return {
        "title": title,
        "outline": outline
    }

def process_pdfs(input_dir, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    for filename in os.listdir(input_dir):
        if filename.lower().endswith('.pdf'):
            pdf_path = os.path.join(input_dir, filename)
            result = extract_outline(pdf_path)
            
            output_filename = os.path.splitext(filename)[0] + '.json'
            output_path = os.path.join(output_dir, output_filename)
            
            with open(output_path, 'w') as f:
                json.dump(result, f, indent=2)

if __name__ == "__main__":
    input_dir = '/app/input'
    output_dir = '/app/output'
    process_pdfs(input_dir, output_dir)