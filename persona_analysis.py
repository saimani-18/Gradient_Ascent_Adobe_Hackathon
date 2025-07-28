import json
import os
import re
from datetime import datetime
from collections import defaultdict
import pdfplumber
from sentence_transformers import SentenceTransformer, util
import numpy as np

class PersonaAnalyzer:
    def __init__(self):
        self.en_model = SentenceTransformer('all-MiniLM-L6-v2')
        try:
            self.multilingual_model = SentenceTransformer('paraphrase-xlm-r-multilingual-v1')
        except:
            self.multilingual_model = self.en_model
    
    def extract_sections(self, pdf_path):
        sections = []
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                text = page.extract_text()
                if not text:
                    continue
                paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
                
                for para in paragraphs:
                    
                    if len(para.split()) < 15 and (para.isupper() or para.endswith(':')):
                        sections.append({
                            "text": para,
                            "page": page_num,
                            "document": os.path.basename(pdf_path)
                        })
                    else:
                        sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', para)
                        for sent in sentences:
                            if len(sent.split()) > 5:  
                                sections.append({
                                    "text": sent,
                                    "page": page_num,
                                    "document": os.path.basename(pdf_path)
                                })
        return sections
    
    def analyze_for_persona(self, documents, persona, job):
        all_sections = []
        for doc in documents:
            all_sections.extend(self.extract_sections(doc))
        
        if self.is_non_english(job):
            job_embedding = self.multilingual_model.encode(job)
        else:
            job_embedding = self.en_model.encode(job)
        
        scored_sections = []
        for section in all_sections:
            text = section['text']
            
            if self.is_non_english(text):
                text_embedding = self.multilingual_model.encode(text)
                similarity = util.cos_sim(job_embedding, text_embedding).item()
            else:
                text_embedding = self.en_model.encode(text)
                similarity = util.cos_sim(job_embedding, text_embedding).item()
            
            keywords = re.findall(r'\w+', job.lower())
            keyword_score = sum(1 for kw in keywords if kw in text.lower()) / len(keywords) if keywords else 0
            
            total_score = similarity * 0.8 + keyword_score * 0.2
            scored_sections.append({
                **section,
                "importance_score": total_score,
                "is_english": not self.is_non_english(text)
            })
        
        scored_sections.sort(key=lambda x: x['importance_score'], reverse=True)
        
        output = {
            "metadata": {
                "input_documents": [os.path.basename(d) for d in documents],
                "persona": persona,
                "job_to_be_done": job,
                "processing_timestamp": datetime.utcnow().isoformat()
            },
            "extracted_sections": [{
                "document": s['document'],
                "page_number": s['page'],
                "section_title": s['text'][:100] + "..." if len(s['text']) > 100 else s['text'],
                "importance_rank": idx + 1,
                "language": "en" if s['is_english'] else "multilingual"
            } for idx, s in enumerate(scored_sections[:20])],  # Top 20 sections
            "sub_section_analysis": [{
                "document": s['document'],
                "page_number": s['page'],
                "refined_text": self.refine_text(s['text']),
                "relevance_to_job": f"{s['importance_score']:.2f}"
            } for s in scored_sections[:10]]  # Top 10 subsections
        }
        
        return output
    
    def refine_text(self, text):
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def is_non_english(self, text):
        return bool(re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', text))  # Japanese/Chinese chars

def process_persona_analysis(input_dir, persona_file, output_dir):
    analyzer = PersonaAnalyzer()
    with open(persona_file, 'r') as f:
        persona_data = json.load(f)
    
    persona = persona_data.get('persona', '')
    job = persona_data.get('job_to_be_done', '')
    
    documents = [os.path.join(input_dir, f) for f in os.listdir(input_dir) if f.lower().endswith('.pdf')]
    
    if not documents:
        raise ValueError("No PDF documents found in input directory")
    
    result = analyzer.analyze_for_persona(documents, persona, job)
    
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'persona_analysis_output.json')
    
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)

if __name__ == "__main__":
    input_dir = '/app/input'
    persona_file = '/app/persona.json'
    output_dir = '/app/output'
    process_persona_analysis(input_dir, persona_file, output_dir)