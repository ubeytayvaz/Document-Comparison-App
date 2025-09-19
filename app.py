import streamlit as st
import fitz  # PyMuPDF kütüphanesi
import difflib
import base64
import os
import tempfile
import subprocess # Word'den PDF'e dönüştürme için eklendi

# Sayfa yapılandırmasını geniş olarak ayarlayarak karşılaştırma için daha fazla alan sağlıyoruz
st.set_page_config(layout="wide", page_title="Görsel Döküman Karşılaştırma Aracı")

def convert_to_pdf_bytes(uploaded_file):
    """
    Yüklenen dosyanın türünü kontrol eder ve Word belgesiyse PDF byte'larına dönüştürür.
    Bu işlem için sistemde LibreOffice'in yüklü olması gerekir.
    Zaten PDF ise doğrudan byte'ları döndürür.
    """
    file_bytes = uploaded_file.getvalue()
    file_name = uploaded_file.name

    if file_name.lower().endswith(('.docx', '.doc')):
        try:
            st.info(f"'{file_name}' dosyası PDF'e dönüştürülüyor...")
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_word_path = os.path.join(temp_dir, file_name)
                
                # Yüklenen Word dosyasını geçici bir yola yaz
                with open(temp_word_path, "wb") as f:
                    f.write(file_bytes)

                # LibreOffice'i komut satırından çağırarak PDF'e dönüştür
                try:
                    subprocess.run(
                        ['libreoffice', '--headless', '--convert-to', 'pdf', temp_word_path, '--outdir', temp_dir],
                        check=True,
                        capture_output=True
                    )
                except FileNotFoundError:
                    st.error("HATA: Word dosyası dönüştürme başarısız.")
                    st.warning("Bu özelliğin çalışması için sisteminizde LibreOffice'in yüklü olması gerekmektedir. Lütfen LibreOffice'i yükleyip tekrar deneyin.")
                    return None
                except subprocess.CalledProcessError as e:
                    st.error(f"LibreOffice dönüştürme sırasında bir hata verdi. Lütfen dosyanın bozuk olmadığından emin olun. Hata detayı: {e.stderr.decode()}")
                    return None

                # Dönüştürülen PDF'in yolunu oluştur ve oku
                pdf_filename = os.path.splitext(file_name)[0] + ".pdf"
                temp_pdf_path = os.path.join(temp_dir, pdf_filename)

                if os.path.exists(temp_pdf_path):
                    with open(temp_pdf_path, "rb") as f:
                        pdf_bytes = f.read()
                    st.info(f"'{file_name}' başarıyla dönüştürüldü.")
                    return pdf_bytes
                else:
                    st.error(f"Dönüştürme sonrası PDF dosyası bulunamadı. Lütfen LibreOffice'in düzgün çalıştığından emin olun.")
                    return None

        except Exception as conversion_error:
            st.error(f"'{file_name}' dosyası dönüştürülürken genel bir hata oluştu: {conversion_error}")
            return None
    else:
        # Dosya zaten PDF ise byte'ları doğrudan döndür
        return file_bytes

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

def render_all_pages_view(pdf_bytes1, pdf_bytes2):
    """
    Vurgulanmış PDF'leri sayfa sayfa resim olarak yan yana, alt alta gösterir.
    """
    doc1 = fitz.open(stream=pdf_bytes1, filetype="pdf")
    doc2 = fitz.open(stream=pdf_bytes2, filetype="pdf")
    
    max_pages = max(doc1.page_count, doc2.page_count)

    st.markdown("---") # Ayırıcı çizgi

    for i in range(max_pages):
        col1, col2 = st.columns(2)

        with col1:
            if i < doc1.page_count:
                page1 = doc1.load_page(i)
                # Görüntü boyutunu ayarlamak için DPI (dots per inch) değeri
                pix = page1.get_pixmap(dpi=150) 
                img_bytes = pix.tobytes("png")
                st.image(img_bytes, use_container_width=True)
            else:
                # Boş sayfalar için yer tutucu
                st.markdown("&nbsp;", unsafe_allow_html=True)
        
        with col2:
            if i < doc2.page_count:
                page2 = doc2.load_page(i)
                pix = page2.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("png")
                st.image(img_bytes, use_container_width=True)
            else:
                # Boş sayfalar için yer tutucu
                st.markdown("&nbsp;", unsafe_allow_html=True)

    doc1.close()
    doc2.close()


# --- Streamlit Arayüzü ---
st.title("📄 Görsel Döküman Karşılaştırma ve Fark Vurgulama Aracı")
st.markdown("""
<div style="background-color: #e6f3ff; border-left: 5px solid #1a73e8; padding: 10px; border-radius: 5px; margin-bottom: 1rem;">
Soldaki alana <b>eski</b> versiyonu, sağdaki alana <b>yeni</b> versiyonu yükleyerek aradaki farkları görebilirsiniz. PDF ve Word (.docx, .doc) formatları desteklenmektedir.
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
        "Lütfen eski dökümanı seçin (PDF, DOCX)",
        type=['pdf', 'docx', 'doc'],
        key="file1"
    )

with col2:
    st.header("Yeni Versiyon (Sağ)")
    uploaded_file2 = st.file_uploader(
        "Lütfen yeni dökümanı seçin (PDF, DOCX)",
        type=['pdf', 'docx', 'doc'],
        key="file2"
    )

if uploaded_file1 and uploaded_file2:
    
    pdf_bytes1 = convert_to_pdf_bytes(uploaded_file1)
    pdf_bytes2 = convert_to_pdf_bytes(uploaded_file2)
    
    # Sadece iki dosya da başarıyla işlendiyse devam et
    if pdf_bytes1 and pdf_bytes2:
        with st.spinner("Dökümanlar karşılaştırılıyor ve farklılıklar vurgulanıyor... Bu işlem dökümanların boyutuna göre zaman alabilir."):
            try:
                # Karşılaştırma fonksiyonunu çağır
                highlighted_pdf1_bytes, highlighted_pdf2_bytes = compare_and_highlight(pdf_bytes1, pdf_bytes2)

                st.success("Karşılaştırma tamamlandı! Vurgulanmış versiyonları aşağıda görebilir veya indirebilirsiniz.")
                
                # İndirme butonları
                dl_col1, dl_col2 = st.columns(2)
                with dl_col1:
                    st.download_button(
                        label="Eski Versiyonu İndir (Vurgulanmış)",
                        data=highlighted_pdf1_bytes,
                        file_name=f"vurgulanmis_{uploaded_file1.name.rsplit('.', 1)[0]}.pdf",
                        mime="application/pdf"
                    )
                with dl_col2:
                    st.download_button(
                        label="Yeni Versiyonu İndir (Vurgulanmış)",
                        data=highlighted_pdf2_bytes,
                        file_name=f"vurgulanmis_{uploaded_file2.name.rsplit('.', 1)[0]}.pdf",
                        mime="application/pdf"
                    )
                
                # Sonuçları sayfa sayfa resim olarak göster
                render_all_pages_view(highlighted_pdf1_bytes, highlighted_pdf2_bytes)


            except Exception as e:
                st.error(f"Dökümanlar işlenirken bir hata oluştu: {e}")
                st.error("Lütfen dosyaların geçerli ve metin okunabilir olduğundan emin olun. Taranmış (resim tabanlı) dökümanlar desteklenmemektedir.")

