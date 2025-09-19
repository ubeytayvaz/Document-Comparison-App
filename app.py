import streamlit as st
import fitz  # PyMuPDF kütüphanesi
import difflib
import base64
import re # Metin normalleştirme için eklendi

# Sayfa yapılandırmasını geniş olarak ayarlayarak karşılaştırma için daha fazla alan sağlıyoruz
st.set_page_config(layout="wide", page_title="Görsel PDF Karşılaştırma Aracı")

def normalize_text(text):
    """
    Karşılaştırma doğruluğunu artırmak için metni normalleştirir.
    Küçük harfe çevirir, fazla boşlukları kaldırır ve noktalama işaretlerini siler.
    """
    text = text.lower()
    # Türkçe karakterleri de içerecek şekilde noktalama işaretlerini kaldıran regex
    text = re.sub(r'[^a-z0-9\sçğıöşü]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def align_pages(doc1, doc2):
    """
    İki dokümandaki sayfaları içeriklerine göre karşılaştırır, eklenen/silinen
    sayfaları hesaba katarak en iyi hizalamayı bulur.
    Her bir tuple'ın eşleşen sayfa indekslerini içerdiği bir liste döndürür.
    (doc1_sayfa_indeksi, doc2_sayfa_indeksi). None değeri boş bir sayfayı belirtir.
    """
    pages_text1 = [normalize_text(page.get_text("text")) for page in doc1]
    pages_text2 = [normalize_text(page.get_text("text")) for page in doc2]

    page_matcher = difflib.SequenceMatcher(None, pages_text1, pages_text2, autojunk=False)
    
    aligned_pairs = []
    for tag, i1, i2, j1, j2 in page_matcher.get_opcodes():
        if tag == 'equal':
            for i in range(i2 - i1):
                aligned_pairs.append((i1 + i, j1 + i))
        elif tag == 'delete':
            for i in range(i1, i2):
                aligned_pairs.append((i, None))
        elif tag == 'insert':
            for j in range(j1, j2):
                aligned_pairs.append((None, j))
        elif tag == 'replace':
            len1 = i2 - i1
            len2 = j2 - j1
            common_len = min(len1, len2)
            for i in range(common_len):
                aligned_pairs.append((i1 + i, j1 + i))
            if len1 > len2:
                for i in range(common_len, len1):
                    aligned_pairs.append((i1 + i, None))
            elif len2 > len1:
                for j in range(common_len, len2):
                    aligned_pairs.append((None, j1 + j))
    return aligned_pairs

def compare_and_highlight(doc1, doc2, aligned_pairs):
    """
    Hizalanmış sayfa çiftlerine göre iki PDF'i karşılaştırır, farkları vurgular
    ve kelime bazında değişiklik istatistiklerini hesaplar.
    """
    # Değişiklik özeti için sayaçlar
    summary = {'added': 0, 'deleted': 0, 'moved': 0}
    modified_pages_count = 0

    for idx1, idx2 in aligned_pairs:
        if idx1 is None or idx2 is None:
            continue

        page_modified = False
        page1 = doc1.load_page(idx1)
        page2 = doc2.load_page(idx2)

        words1 = page1.get_text("words")
        words2 = page2.get_text("words")
        
        text1 = [w[4] for w in words1]
        text2 = [w[4] for w in words2]

        matcher = difflib.SequenceMatcher(None, text1, text2, autojunk=False)
        opcodes = matcher.get_opcodes()

        for tag, i1, i2, j1, j2 in opcodes:
            if tag != 'equal':
                page_modified = True

            if tag == 'delete':
                summary['deleted'] += (i2 - i1)
                for k in range(i1, i2):
                    highlight = page1.add_highlight_annot(fitz.Rect(words1[k][:4]))
                    highlight.set_colors(stroke=(1, 0, 0)) # Kırmızı
                    highlight.update()
            
            elif tag == 'insert':
                summary['added'] += (j2 - j1)
                for k in range(j1, j2):
                    highlight = page2.add_highlight_annot(fitz.Rect(words2[k][:4]))
                    highlight.set_colors(stroke=(1, 1, 0)) # Sarı
                    highlight.update()

            elif tag == 'replace':
                summary['deleted'] += (i2 - i1)
                summary['added'] += (j2 - j1)
                for k in range(i1, i2):
                    highlight = page1.add_highlight_annot(fitz.Rect(words1[k][:4]))
                    highlight.set_colors(stroke=(1, 0, 0))
                    highlight.update()
                for k in range(j1, j2):
                    highlight = page2.add_highlight_annot(fitz.Rect(words2[k][:4]))
                    highlight.set_colors(stroke=(1, 1, 0))
                    highlight.update()
            
            elif tag == 'equal':
                 for k in range(i2 - i1):
                    word1_data = words1[i1 + k]
                    word2_data = words2[j1 + k]
                    rect1 = fitz.Rect(word1_data[:4])
                    rect2 = fitz.Rect(word2_data[:4])
                    if abs(rect1.x0 - rect2.x0) > 10 or abs(rect1.y0 - rect2.y0) > 10:
                        page_modified = True
                        summary['moved'] += 1
                        h1 = page1.add_highlight_annot(rect1)
                        h1.set_colors(stroke=(0.5, 0.8, 1)) # Açık Mavi
                        h1.update()
                        h2 = page2.add_highlight_annot(rect2)
                        h2.set_colors(stroke=(0.5, 0.8, 1))
                        h2.update()
        
        if page_modified:
            modified_pages_count += 1

    summary['modified_pages'] = modified_pages_count
    output_bytes1 = doc1.tobytes()
    output_bytes2 = doc2.tobytes()

    return output_bytes1, output_bytes2, summary

def render_all_pages_view(pdf_bytes1, pdf_bytes2, aligned_pairs):
    """
    Vurgulanmış PDF'leri hizalanmış plana göre sayfa sayfa resim olarak gösterir.
    """
    doc1 = fitz.open(stream=pdf_bytes1, filetype="pdf")
    doc2 = fitz.open(stream=pdf_bytes2, filetype="pdf")
    
    st.markdown("---") 

    for idx1, idx2 in aligned_pairs:
        col1, col2 = st.columns(2)
        with col1:
            if idx1 is not None:
                page1 = doc1.load_page(idx1)
                pix = page1.get_pixmap(dpi=150) 
                img_bytes = pix.tobytes("png")
                st.image(img_bytes, use_container_width=True)
            else:
                st.markdown("<div style='height: 400px; border: 2px dashed #ccc; display: flex; align-items: center; justify-content: center; background-color: #fafafa; border-radius: 5px;'><span style='color: #888; font-style: italic;'>Bu pozisyona yeni sayfa eklendi</span></div>", unsafe_allow_html=True)
        with col2:
            if idx2 is not None:
                page2 = doc2.load_page(idx2)
                pix = page2.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("png")
                st.image(img_bytes, use_container_width=True)
            else:
                st.markdown("<div style='height: 400px; border: 2px dashed #ccc; display: flex; align-items: center; justify-content: center; background-color: #fafafa; border-radius: 5px;'><span style='color: #888; font-style: italic;'>Bu sayfadaki içerik silindi</span></div>", unsafe_allow_html=True)
    doc1.close()
    doc2.close()

# --- Streamlit Arayüzü ---
st.title("📄 Görsel PDF Karşılaştırma ve Fark Vurgulama Aracı")
st.markdown("""
<div style="background-color: #e6f3ff; border-left: 5px solid #1a73e8; padding: 10px; border-radius: 5px; margin-bottom: 1rem;">
Soldaki alana <b>eski</b> versiyonu, sağdaki alana <b>yeni</b> versiyonu yükleyerek aradaki farkları görebilirsiniz. Sadece PDF formatı desteklenmektedir.
<ul>
    <li><b><span style='color:red;'>Kırmızı Vurgu</span></b>: Eski dökümanda olup yeni dökümanda olmayan (silinmiş) metinler.</li>
    <li><b><span style='color:darkgoldenrod;'>Sarı Vurgu</span></b>: Yeni dökümanda olup eski dökümanda olmayan (eklenmiş) metinler.</li>
    <li><b><span style='color:cornflowerblue;'>Açık Mavi Vurgu</span></b>: Her iki dökümanda da bulunan ancak yeri değişmiş metinler.</li>
</ul>
</div>
""", unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    st.header("Eski Versiyon (Sol)")
    uploaded_file1 = st.file_uploader("Lütfen eski PDF dosyasını seçin", type=['pdf'], key="file1")
with col2:
    st.header("Yeni Versiyon (Sağ)")
    uploaded_file2 = st.file_uploader("Lütfen yeni PDF dosyasını seçin", type=['pdf'], key="file2")

if uploaded_file1 and uploaded_file2:
    pdf_bytes1 = uploaded_file1.getvalue()
    pdf_bytes2 = uploaded_file2.getvalue()
    
    with st.spinner("PDF'ler hizalanıyor ve karşılaştırılıyor... Bu işlem dökümanların boyutuna göre zaman alabilir."):
        try:
            doc1 = fitz.open(stream=pdf_bytes1, filetype="pdf")
            doc2 = fitz.open(stream=pdf_bytes2, filetype="pdf")

            aligned_pairs = align_pages(doc1, doc2)
            highlighted_pdf1_bytes, highlighted_pdf2_bytes, summary = compare_and_highlight(doc1, doc2, aligned_pairs)

            doc1.close()
            doc2.close()

            st.success("Karşılaştırma tamamlandı!")
            
            # --- YENİ: Değişiklik Özeti Raporu ---
            pages_added = sum(1 for p in aligned_pairs if p[0] is None)
            pages_deleted = sum(1 for p in aligned_pairs if p[1] is None)
            
            st.info(f"""
            **Değişiklik Özeti:**
            - **Eklenen Sayfa Sayısı:** `{pages_added}`
            - **Silinen Sayfa Sayısı:** `{pages_deleted}`
            - **İçeriği Değişen Sayfa Sayısı:** `{summary['modified_pages']}`
            - **Eklenen Kelime Sayısı:** `{summary['added']}`
            - **Silinen Kelime Sayısı:** `{summary['deleted']}`
            - **Yeri Değişen Kelime Sayısı:** `{summary['moved']}`
            """)

            # İndirme butonları
            dl_col1, dl_col2 = st.columns(2)
            with dl_col1:
                st.download_button(
                    label="Eski Versiyonu İndir (Vurgulanmış)",
                    data=highlighted_pdf1_bytes,
                    file_name=f"vurgulanmis_{uploaded_file1.name}",
                    mime="application/pdf"
                )
            with dl_col2:
                st.download_button(
                    label="Yeni Versiyonu İndir (Vurgulanmış)",
                    data=highlighted_pdf2_bytes,
                    file_name=f"vurgulanmis_{uploaded_file2.name}",
                    mime="application/pdf"
                )
            
            render_all_pages_view(highlighted_pdf1_bytes, highlighted_pdf2_bytes, aligned_pairs)

        except Exception as e:
            st.error(f"Dökümanlar işlenirken bir hata oluştu: {e}")
            st.error("Lütfen dosyaların geçerli ve metin okunabilir olduğundan emin olun. Taranmış (resim tabanlı) PDF'ler desteklenmemektedir.")

