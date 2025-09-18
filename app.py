import streamlit as st
import docx
from PyPDF2 import PdfReader
import difflib
import io
import fitz  # PyMuPDF kütüphanesi
from PIL import Image

# Sayfa yapılandırmasını geniş olarak ayarlayarak karşılaştırma için daha fazla alan sağlıyoruz
st.set_page_config(layout="wide", page_title="Döküman Karşılaştırma Aracı")

def get_text_from_file(uploaded_file):
    """
    Yüklenen dosyayı türüne göre okur ve metin içeriğini döndürür.
    Desteklenen formatlar: .txt, .pdf, .docx
    """
    text = ""
    # Dosyanın var olup olmadığını kontrol et
    if uploaded_file is not None:
        try:
            # Dosya imlecini başa al
            uploaded_file.seek(0)
            # Dosya türüne göre işlem yap
            if uploaded_file.type == "text/plain":
                # Txt dosyaları için
                stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8"))
                text = stringio.read()
            elif uploaded_file.type == "application/pdf":
                # PDF dosyaları için
                pdf_reader = PdfReader(uploaded_file)
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                # Docx (Word) dosyaları için
                doc = docx.Document(uploaded_file)
                for para in doc.paragraphs:
                    text += para.text + "\n"
        except Exception as e:
            st.error(f"Dosya okunurken bir hata oluştu: {uploaded_file.name}. Hata: {e}")
            return None
    return text

def render_pdf_to_images(uploaded_file):
    """
    Yüklenen PDF dosyasının sayfalarını görsellere dönüştürür.
    """
    images = []
    try:
        # Dosya imlecini başa al
        uploaded_file.seek(0)
        # Dosya içeriğini byte olarak oku
        pdf_bytes = uploaded_file.read()
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)
            pix = page.get_pixmap()
            img_data = pix.tobytes("png")
            image = Image.open(io.BytesIO(img_data))
            images.append(image)
        pdf_document.close()
    except Exception as e:
        st.error(f"PDF görselleştirilirken bir hata oluştu: {uploaded_file.name}. Hata: {e}")
        return []
    return images


# Ana başlık ve bilgilendirme
st.title("📄 Gelişmiş Döküman Karşılaştırma Aracı")
st.info("Karşılaştırmak istediğiniz iki dökümanı (Word, PDF, veya TXT) yükleyerek metinsel farkları görebilirsiniz. Eğer iki dosya da PDF ise, görsel olarak da karşılaştırılacaktır.")

# Dosya yükleme alanlarını iki sütunda göster
col1, col2 = st.columns(2)

with col1:
    st.subheader("Birinci Dosya")
    uploaded_file1 = st.file_uploader(
        "Lütfen birinci dosyayı seçin",
        type=['txt', 'pdf', 'docx'],
        key="file1",
        help="Karşılaştırılacak ilk dosyayı buraya yükleyin."
    )

with col2:
    st.subheader("İkinci Dosya")
    uploaded_file2 = st.file_uploader(
        "Lütfen ikinci dosyayı seçin",
        type=['txt', 'pdf', 'docx'],
        key="file2",
        help="Karşılaştırılacak ikinci dosyayı buraya yükleyin."
    )

# İki dosya da yüklendiğinde karşılaştırmayı yap
if uploaded_file1 and uploaded_file2:
    
    # Eğer her iki dosya da PDF ise, görsel karşılaştırma yap
    if uploaded_file1.type == "application/pdf" and uploaded_file2.type == "application/pdf":
        st.header("Görsel Karşılaştırma", divider='rainbow')
        with st.spinner("PDF sayfaları görsellere dönüştürülüyor... Lütfen bekleyin."):
            images1 = render_pdf_to_images(uploaded_file1)
            images2 = render_pdf_to_images(uploaded_file2)

            if images1 and images2:
                st.success("PDF'ler görselleştirildi. Sayfaları aşağıda karşılaştırabilirsiniz.")
                
                # İki PDF'in sayfa sayılarından büyük olanı al
                max_pages = max(len(images1), len(images2))
                
                for i in range(max_pages):
                    st.markdown(f"--- \n ### Sayfa {i+1}")
                    img_col1, img_col2 = st.columns(2)
                    
                    # Birinci PDF'in sayfasını göster
                    with img_col1:
                        if i < len(images1):
                            st.image(images1[i], caption=f"{uploaded_file1.name} - Sayfa {i+1}", use_column_width=True)
                        else:
                            st.warning(f"Bu dökümanda {i+1}. sayfa bulunmuyor.")
                    
                    # İkinci PDF'in sayfasını göster
                    with img_col2:
                        if i < len(images2):
                            st.image(images2[i], caption=f"{uploaded_file2.name} - Sayfa {i+1}", use_column_width=True)
                        else:
                            st.warning(f"Bu dökümanda {i+1}. sayfa bulunmuyor.")

    # Metinsel karşılaştırma her zaman yapılır
    st.header("Metinsel Karşılaştırma", divider='rainbow')
    with st.spinner("Dosyalar okunuyor ve metinler karşılaştırılıyor... Lütfen bekleyin."):
        # Dosyalardan metinleri al
        text1 = get_text_from_file(uploaded_file1)
        text2 = get_text_from_file(uploaded_file2)

        # Metinler başarıyla alındıysa devam et
        if text1 is not None and text2 is not None:
            # Metinleri satırlara ayır
            lines1 = text1.splitlines()
            lines2 = text2.splitlines()

            # HTMLDiff kullanarak farkları gösteren bir HTML tablosu oluştur
            html_diff = difflib.HtmlDiff(wrapcolumn=80).make_table(
                lines1,
                lines2,
                fromdesc=f"Dosya 1: {uploaded_file1.name}",
                todesc=f"Dosya 2: {uploaded_file2.name}"
            )

            st.success("Metinsel karşılaştırma tamamlandı! Sonuçlar aşağıdadır.")

            # Oluşturulan HTML'i ekranda göster
            st.markdown(html_diff, unsafe_allow_html=True)

elif uploaded_file1 and not uploaded_file2:
    st.warning("Lütfen karşılaştırma yapmak için ikinci dosyayı da yükleyin.")
elif not uploaded_file1 and uploaded_file2:
    st.warning("Lütfen karşılaştırma yapmak için birinci dosyayı da yükleyin.")

