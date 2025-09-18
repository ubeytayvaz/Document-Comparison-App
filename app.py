import streamlit as st
import fitz  # PyMuPDF kütüphanesi
import difflib
import base64

# Sayfa yapılandırmasını geniş olarak ayarlayarak karşılaştırma için daha fazla alan sağlıyoruz
st.set_page_config(layout="wide", page_title="Görsel PDF Karşılaştırma Aracı")

def compare_and_highlight(pdf_bytes1, pdf_bytes2):
    """
    İki PDF'i karşılaştırır, farkları bulur ve yeni PDF'ler üzerinde vurgular.
    - Silinen metinler (sadece ilk PDF'te olanlar) kırmızı ile vurgulanır.
    - Eklenen metinler (sadece ikinci PDF'te olanlar) sarı ile vurgulanır.
    - Yeri değişen metinler her iki PDF'te de açık mavi ile vurgulanır.
    """
    doc1 = fitz.open(stream=pdf_bytes1, filetype="pdf")
    doc2 = fitz.open(stream=pdf_bytes2, filetype="pdf")

    # Karşılaştırılacak sayfa sayısı, en uzun PDF'e göre belirlenir
    max_pages = max(doc1.page_count, doc2.page_count)

    for i in range(max_pages):
        # Sayfaları al, eğer bir PDF daha kısaysa boş sayfa olarak kabul et
        page1 = doc1.load_page(i) if i < doc1.page_count else None
        page2 = doc2.load_page(i) if i < doc2.page_count else None

        # Sayfa boşsa, atla
        if page1 is None or page2 is None:
            continue

        # Karşılaştırma için sayfalardaki kelimeleri ve konumlarını al
        words1 = page1.get_text("words")
        words2 = page2.get_text("words")
        
        # Sadece kelime metinlerini içeren listeler oluştur
        text1 = [w[4] for w in words1]
        text2 = [w[4] for w in words2]

        # difflib ile kelime dizileri arasındaki farkları bul
        matcher = difflib.SequenceMatcher(None, text1, text2, autojunk=False)
        opcodes = matcher.get_opcodes()

        # Farklılıklara göre vurgulamaları ekle
        for tag, i1, i2, j1, j2 in opcodes:
            if tag == 'replace' or tag == 'delete':
                # Kırmızı: Eski dökümanda silinmiş veya değiştirilmiş metinler
                for k in range(i1, i2):
                    word_bbox = fitz.Rect(words1[k][:4])
                    highlight = page1.add_highlight_annot(word_bbox)
                    highlight.set_colors(stroke=(1, 0, 0)) # Kırmızı renk
                    highlight.update()

            if tag == 'replace' or tag == 'insert':
                # Sarı: Yeni dökümana eklenmiş veya değiştirilmiş metinler
                for k in range(j1, j2):
                    word_bbox = fitz.Rect(words2[k][:4])
                    highlight = page2.add_highlight_annot(word_bbox)
                    highlight.set_colors(stroke=(1, 1, 0)) # Sarı renk
                    highlight.update()
            
            if tag == 'equal':
                 # Mavi: Yeri değişmiş metinler
                 for k in range(i2 - i1):
                    word1_data = words1[i1 + k]
                    word2_data = words2[j1 + k]
                    
                    rect1 = fitz.Rect(word1_data[:4])
                    rect2 = fitz.Rect(word2_data[:4])

                    # Kelimenin pozisyonu belirli bir eşikten fazla değiştiyse
                    if abs(rect1.x0 - rect2.x0) > 10 or abs(rect1.y0 - rect2.y0) > 10:
                        h1 = page1.add_highlight_annot(rect1)
                        h1.set_colors(stroke=(0.5, 0.8, 1)) # Açık Mavi
                        h1.update()
                        
                        h2 = page2.add_highlight_annot(rect2)
                        h2.set_colors(stroke=(0.5, 0.8, 1)) # Açık Mavi
                        h2.update()

    # Değişiklikler yapılmış PDF'leri byte olarak kaydet
    output_bytes1 = doc1.tobytes()
    output_bytes2 = doc2.tobytes()

    doc1.close()
    doc2.close()

    return output_bytes1, output_bytes2

def display_pdf(pdf_bytes):
    """PDF'i base64 formatına çevirip iframe içinde gösterir."""
    base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800" type="application/pdf"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)

# --- Streamlit Arayüzü ---
st.title("📄 Görsel PDF Karşılaştırma ve Fark Vurgulama Aracı")
st.info("""
Soldaki alana **eski** versiyonu, sağdaki alana **yeni** versiyonu yükleyerek aradaki farkları görebilirsiniz.
- **<span style='color:red; font-weight:bold;'>Kırmızı Vurgu</span>**: Eski dökümanda olup yeni dökümanda olmayan (silinmiş) metinler.
- **<span style='color:gold; font-weight:bold;'>Sarı Vurgu</span>**: Yeni dökümanda olup eski dökümanda olmayan (eklenmiş) metinler.
- **<span style='color:cornflowerblue; font-weight:bold;'>Açık Mavi Vurgu</span>**: Her iki dökümanda da bulunan ancak yeri değişmiş metinler.
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
    with st.spinner("PDF'ler karşılaştırılıyor ve farklılıklar vurgulanıyor... Bu işlem dökümanların boyutuna göre zaman alabilir."):
        try:
            pdf_bytes1 = uploaded_file1.getvalue()
            pdf_bytes2 = uploaded_file2.getvalue()

            # Karşılaştırma fonksiyonunu çağır
            highlighted_pdf1_bytes, highlighted_pdf2_bytes = compare_and_highlight(pdf_bytes1, pdf_bytes2)

            st.success("Karşılaştırma tamamlandı! Vurgulanmış PDF'ler aşağıdadır.")
            
            # Sonuçları göster
            display_col1, display_col2 = st.columns(2)
            with display_col1:
                display_pdf(highlighted_pdf1_bytes)
            with display_col2:
                display_pdf(highlighted_pdf2_bytes)

        except Exception as e:
            st.error(f"PDF'ler işlenirken bir hata oluştu: {e}")
            st.error("Lütfen PDF dosyalarının geçerli ve metin okunabilir olduğundan emin olun. Taranmış (resim tabanlı) PDF'ler desteklenmemektedir.")

