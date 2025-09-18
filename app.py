import streamlit as st
import docx
from PyPDF2 import PdfReader
import difflib
import io

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

# Ana başlık ve bilgilendirme
st.title("📄 Döküman Karşılaştırma Aracı")
st.info("Karşılaştırmak istediğiniz iki dökümanı (Word, PDF, veya TXT) aşağıya yükleyerek aralarındaki farkları görebilirsiniz.")

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
    with st.spinner("Dosyalar okunuyor ve karşılaştırılıyor... Lütfen bekleyin."):
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

            st.success("Karşılaştırma tamamlandı! Sonuçlar aşağıdadır.")
            st.header("Karşılaştırma Sonucu", divider='rainbow')

            # Oluşturulan HTML'i ekranda göster
            st.markdown(html_diff, unsafe_allow_html=True)

            # İsteğe bağlı olarak orijinal metinleri de bir expander içinde göster
            with st.expander("Yüklenen Dosyaların Orijinal Metinlerini Görüntüle"):
                col_exp1, col_exp2 = st.columns(2)
                with col_exp1:
                    st.text_area(f"Metin 1: {uploaded_file1.name}", text1, height=400)
                with col_exp2:
                    st.text_area(f"Metin 2: {uploaded_file2.name}", text2, height=400)

elif uploaded_file1 and not uploaded_file2:
    st.warning("Lütfen karşılaştırma yapmak için ikinci dosyayı da yükleyin.")
elif not uploaded_file1 and uploaded_file2:
    st.warning("Lütfen karşılaştırma yapmak için birinci dosyayı da yükleyin.")
