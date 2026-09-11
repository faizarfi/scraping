import io
import re
import logging
import pandas as pd
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

logger = logging.getLogger(__name__)

KARANGANYAR_DISTRICTS = [
    'Colomadu', 'Gondangrejo', 'Jaten', 'Jatipuro', 'Jatiyoso', 
    'Jenawi', 'Jumantono', 'Jumapolo', 'Karanganyar', 'Karangpandan', 
    'Kebakkramat', 'Kerjo', 'Matesih', 'Mojogedang', 'Ngargoyoso', 
    'Tasikmadu', 'Tawangmangu'
]

def resolve_district(place):
    """
    Pastikan kolom Kecamatan di Excel selalu terisi rapi:
    1. Ambil district tersimpan
    2. Fallback: Ekstrak nama kecamatan dari alamat lengkap
    3. Fallback: Ekstrak dari query pencarian
    4. Default: 'Kabupaten Karanganyar'
    """
    if place.district and place.district.strip():
        return place.district.strip()

    addr = (place.address or "").lower()
    for d in KARANGANYAR_DISTRICTS:
        if d.lower() in addr:
            return d

    sq = (place.search_query or "").lower()
    for d in KARANGANYAR_DISTRICTS:
        if d.lower() in sq:
            return d

    return "Kabupaten Karanganyar"


def build_dataframe_from_queryset(queryset):
    """
    Ubah queryset Place menjadi Pandas DataFrame yang rapi untuk diekspor
    """
    data = []
    for idx, p in enumerate(queryset, start=1):
        data.append({
            'No': idx,
            'Nama Tempat': p.name,
            'Kategori': p.category or 'Bisnis',
            'Kecamatan': resolve_district(p),
            'Rating': p.rating if p.rating is not None else '',
            'Jumlah Ulasan': p.reviews_count,
            'Alamat': p.address,
            'No Telepon': p.phone,
            'Website': p.website,
            'Link Google Maps': p.google_maps_url,
            'Latitude': p.latitude if p.latitude is not None else '',
            'Longitude': p.longitude if p.longitude is not None else '',
            'Kata Kunci': p.search_query,
            'Waktu Ditemukan': p.created_at.strftime('%Y-%m-%d %H:%M:%S') if p.created_at else ''
        })
    df = pd.DataFrame(data)
    return df


def format_worksheet(worksheet, df):
    """
    Terapkan styling profesional pada worksheet: header tema gelap, border tipis,
    alignment angka/rating, auto-fit lebar kolom, dan link Google Maps yang dapat diklik.
    """
    if df.empty:
        return

    # Styling Header
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    for col_num in range(1, len(df.columns) + 1):
        cell = worksheet.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border

    # Baris isi data
    data_font = Font(name="Segoe UI", size=10)
    link_font = Font(name="Segoe UI", size=10, color="2563EB", underline="single")

    for row_idx, row in enumerate(worksheet.iter_rows(min_row=2, max_row=len(df) + 1, min_col=1, max_col=len(df.columns)), start=2):
        for col_idx, cell in enumerate(row, start=1):
            cell.font = data_font
            cell.border = thin_border
            cell.alignment = Alignment(vertical="center")

            # Kolom Link Google Maps dibuat clickable hyperlink
            col_name = df.columns[col_idx - 1]
            if col_name == 'Link Google Maps' and cell.value and str(cell.value).startswith('http'):
                cell.hyperlink = str(cell.value)
                cell.font = link_font

            if col_name in ['Rating', 'Latitude', 'Longitude', 'No']:
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif col_name == 'Jumlah Ulasan':
                cell.alignment = Alignment(horizontal="right", vertical="center")

    # Auto-adjust column widths
    for col in worksheet.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val = str(cell.value or '')
            if len(val) > max_len:
                max_len = len(val)
        worksheet.column_dimensions[col_letter].width = min(max(max_len + 4, 12), 45)

    worksheet.row_dimensions[1].height = 28


def generate_excel_bytes(queryset, title="Data Google Maps"):
    """
    Hasilkan file Excel (.xlsx) dengan styling rapi.
    Jika terdapat beberapa kategori berbeda, otomatis dibuatkan:
    - Tab Sheet 'Semua Data' (Master gabungan dengan 100% data)
    - Tab Sheet terpisah untuk masing-masing Kategori
    """
    df = build_dataframe_from_queryset(queryset)
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Sheet 1: Master Sheet (Semua Data)
        master_sheet_name = 'Semua Data'
        df.to_excel(writer, index=False, sheet_name=master_sheet_name)
        
        master_ws = writer.sheets.get(master_sheet_name)
        if master_ws is not None:
            try:
                format_worksheet(master_ws, df)
            except Exception as e:
                logger.warning("Gagal format master sheet: %s", e)

        # Tab Sheet Per-Kategori (jika ada data dan kolom Kategori)
        if not df.empty and 'Kategori' in df.columns:
            try:
                # Normalisasi nama kategori (hapus spasi berlebih & Title Case)
                df_work = df.copy()
                df_work['Kategori_Norm'] = (
                    df_work['Kategori']
                    .fillna('Bisnis')
                    .astype(str)
                    .str.strip()
                    .str.title()
                )
                cat_counts = df_work['Kategori_Norm'].value_counts()
                
                # Jika kategori lebih dari 1, buat sub-sheet
                if len(cat_counts) > 1:
                    used_names_lower = {master_sheet_name.lower()}
                    
                    # Jika ada lebih dari 30 variasi kategori mikro, batasi 30 sheet utama
                    # dan sisanya ditampung dalam sheet 'Kategori Lainnya'
                    max_category_sheets = 30
                    top_cats = list(cat_counts.index[:max_category_sheets])
                    other_cats = list(cat_counts.index[max_category_sheets:])
                    
                    for cat_name in top_cats:
                        sub_df = df_work[df_work['Kategori_Norm'] == cat_name].drop(columns=['Kategori_Norm']).copy()
                        if sub_df.empty:
                            continue
                        
                        # Nomor urut baru per sheet kategori
                        sub_df['No'] = range(1, len(sub_df) + 1)
                        
                        # Bersihkan karakter terlarang Excel (\ / ? * : [ ]) dan tanda kutip
                        clean_name = re.sub(r'[\\/*?:\[\]]', '', str(cat_name)).strip().strip("'") or 'Kategori'
                        base_name = clean_name[:25]
                        sheet_name = base_name
                        counter = 2
                        while sheet_name.lower() in used_names_lower:
                            suffix = f"_{counter}"
                            sheet_name = f"{base_name[:31 - len(suffix)]}{suffix}"
                            counter += 1
                        used_names_lower.add(sheet_name.lower())
                        
                        sub_df.to_excel(writer, index=False, sheet_name=sheet_name)
                        
                        # Ambil worksheet secara aman (case-insensitive fallback)
                        ws = writer.sheets.get(sheet_name)
                        if ws is None and hasattr(writer, 'book'):
                            for title_str in writer.book.sheetnames:
                                if title_str.lower() == sheet_name.lower():
                                    ws = writer.book[title_str]
                                    break
                        if ws is not None:
                            try:
                                format_worksheet(ws, sub_df)
                            except Exception as err:
                                logger.warning("Gagal styling sheet %s: %s", sheet_name, err)
                                
                    # Jika terdapat kategori sisa (di atas 30)
                    if other_cats:
                        other_df = df_work[df_work['Kategori_Norm'].isin(other_cats)].drop(columns=['Kategori_Norm']).copy()
                        if not other_df.empty:
                            other_df['No'] = range(1, len(other_df) + 1)
                            clean_name = 'Kategori Lainnya'
                            sheet_name = clean_name
                            counter = 2
                            while sheet_name.lower() in used_names_lower:
                                sheet_name = f"{clean_name} {counter}"
                                counter += 1
                            used_names_lower.add(sheet_name.lower())
                            
                            other_df.to_excel(writer, index=False, sheet_name=sheet_name)
                            ws = writer.sheets.get(sheet_name)
                            if ws is None and hasattr(writer, 'book'):
                                for title_str in writer.book.sheetnames:
                                    if title_str.lower() == sheet_name.lower():
                                        ws = writer.book[title_str]
                                        break
                            if ws is not None:
                                try:
                                    format_worksheet(ws, other_df)
                                except Exception as err:
                                    logger.warning("Gagal styling sheet %s: %s", sheet_name, err)
            except Exception as e:
                logger.exception("Terjadi kesalahan saat memproses tab kategori Excel: %s", e)

    output.seek(0)
    return output.getvalue()



def generate_csv_bytes(queryset):
    """
    Hasilkan file CSV dalam format UTF-8 with BOM (utf-8-sig)
    sehingga langsung kompatibel di Microsoft Excel
    """
    df = build_dataframe_from_queryset(queryset)
    output = io.StringIO()
    # Gunakan utf-8-sig
    df.to_csv(output, index=False, encoding='utf-8-sig')
    return output.getvalue().encode('utf-8-sig')
