import streamlit as st
import fitz  # PyMuPDF kütüphanesi
import difflib

# Sayfa yapılandırmasını geniş olarak ayarlayarak karşılaştırma için daha fazla alan sağlıyoruz
st.set_page_config(layout="wide", page_title="Görsel PDF Karşılaştırma Aracı")

def compare_and_highlight(pdf_bytes1, pdf_bytes2):
    """
    İki PDF'i sıralı olarak karşılaştırır, farkları bulur ve yeni PDF'ler üzerinde vurgular.
    """
    doc1 = fitz.open(stream=pdf_bytes1, filetype="pdf")
    doc2 = fitz.open(stream=pdf_bytes2, filetype="pdf")

    max_pages = max(doc1.page_count, doc2.page_count)

    for i in range(max_pages):
        # Sayfa sayısı farklı olan dökümanlarda kelime karşılaştırması sadece ortak sayfalarda yapılır
        if i >= doc1.page_count or i >= doc2.page_count:
            continue

        page1 = doc1.load_page(i)
        page2 = doc2.load_page(i)

        words1 = page1.get_text("words")
        words2 = page2.get_text("words")
        
        text1 = [w[4] for w in words1]
        text2 = [w[4] for w in words2]

        matcher = difflib.SequenceMatcher(None, text1, text2, autojunk=False)
        opcodes = matcher.get_opcodes()

        for tag, i1, i2, j1, j2 in opcodes:
            if tag == 'replace' or tag == 'delete':
                for k in range(i1, i2):
                    word_bbox = fitz.Rect(words1[k][:4])
                    highlight = page1.add_highlight_annot(word_bbox)
                    highlight.set_colors(stroke=(1, 0, 0)) # Kırmızı
                    highlight.update()

            if tag == 'replace' or tag == 'insert':
                for k in range(j1, j2):
                    word_bbox = fitz.Rect(words2[k][:4])
                    highlight = page2.add_highlight_annot(word_bbox)
                    highlight.set_colors(stroke=(1, 1, 0)) # Sarı
                    highlight.update()
            
            if tag == 'equal':
                 for k in range(i2 - i1):
                    word1_data = words1[i1 + k]
                    word2_data = words2[j1 + k]
                    
                    rect1 = fitz.Rect(word1_data[:4])
                    rect2 = fitz.Rect(word2_data[:4])

                    if abs(rect1.x0 - rect2.x0) > 10 or abs(rect1.y0 - rect2.y0) > 10:
                        h1 = page1.add_highlight_annot(rect1)
                        h1.set_colors(stroke=(0.5, 0.8, 1)) # Açık Mavi
                        h1.update()
                        
                        h2 = page2.add_highlight_annot(rect2)
                        h2.set_colors(stroke=(0.5, 0.8, 1)) # Açık Mavi
                        h2.update()

    output_bytes1 = doc1.tobytes()
    output_bytes2 = doc2.tobytes()
    
    doc1.close()
    doc2.close()

    return output_bytes1, output_bytes2

def render_all_pages_view(pdf_bytes1, pdf_bytes2):
    """
    Vurgulanmış PDF'leri sayfa sayfa resim olarak gösterir.
    """
    doc1 = fitz.open(stream=pdf_bytes1, filetype="pdf")
    doc2 = fitz.open(stream=pdf_bytes2, filetype="pdf")
    
    st.markdown("---") 

    max_pages = max(doc1.page_count, doc2.page_count)

    for i in range(max_pages):
        col1, col2 = st.columns(2)

        with col1:
            if i < doc1.page_count:
                page1 = doc1.load_page(i)
                pix = page1.get_pixmap(dpi=150) 
                img_bytes = pix.tobytes("png")
                st.image(img_bytes, use_container_width=True)
            else:
                st.markdown("<div style='height: 400px;'></div>", unsafe_allow_html=True)
        
        with col2:
            if i < doc2.page_count:
                page2 = doc2.load_page(i)
                pix = page2.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("png")
                st.image(img_bytes, use_container_width=True)
            else:
                st.markdown("<div style='height: 400px;'></div>", unsafe_allow_html=True)

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
    uploaded_file1 = st.file_uploader(
        "Lütfen eski PDF dosyasını seçin",
        type=['pdf'],
        key="file1"
    )

with col2:
    st.header("Yeni Versiyon (Sağ)")
    uploaded_file2 = st.file_uploader(
        "Lütfen yeni PDF dosyasını seçin",
        type=['pdf'],
        key="file2"
    )

if uploaded_file1 and uploaded_file2:
    
    pdf_bytes1 = uploaded_file1.getvalue()
    pdf_bytes2 = uploaded_file2.getvalue()
    
    with st.spinner("PDF'ler karşılaştırılıyor... Bu işlem dökümanların boyutuna göre zaman alabilir."):
        try:
            # Karşılaştır ve vurgula
            highlighted_pdf1_bytes, highlighted_pdf2_bytes = compare_and_highlight(pdf_bytes1, pdf_bytes2)

            st.success("Karşılaştırma tamamlandı! Vurgulanmış versiyonları aşağıda görebilir veya indirebilirsiniz.")
            
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
            
            # Sonuçları göster
            render_all_pages_view(highlighted_pdf1_bytes, highlighted_pdf2_bytes)

        except Exception as e:
            st.error(f"Dökümanlar işlenirken bir hata oluştu: {e}")
            st.error("Lütfen dosyaların geçerli ve metin okunabilir olduğundan emin olun. Taranmış (resim tabanlı) PDF'ler desteklenmemektedir.")

