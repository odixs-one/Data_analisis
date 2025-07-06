import streamlit as st
import pandas as pd
import plotly.express as px
import re  # Untuk ekspresi reguler dalam parsing SKU

# Konfigurasi halaman Streamlit
st.set_page_config(
    layout="wide",
    page_title="Dashboard Analisis Bisnis",
    initial_sidebar_state="expanded"
)


# --- Fungsi untuk Memuat Data ---
# Menggunakan st.cache_data untuk caching data agar aplikasi lebih cepat
@st.cache_data
def load_sku_master(file_uploader):
    """
    Memuat data master SKU dari file Excel yang diunggah.
    File ini diharapkan memiliki kolom 'CODE', 'ARTI', dan 'JENIS'.
    """
    if file_uploader is not None:
        try:
            df_sku_master = pd.read_excel(file_uploader)
            # Membersihkan nama kolom dari spasi berlebih dan karakter baris baru
            df_sku_master.columns = [re.sub(r'\s+', ' ', col).strip() for col in df_sku_master.columns]

            sku_decoder = {}
            if not df_sku_master.empty:
                required_cols = ['CODE', 'ARTI', 'JENIS']
                if not all(col in df_sku_master.columns for col in required_cols):
                    raise ValueError(f"File SKU Master harus memiliki kolom: {', '.join(required_cols)}")

                for index, row in df_sku_master.iterrows():
                    code = str(row.get('CODE', '')).strip().upper()
                    arti = str(row.get('ARTI', '')).strip()
                    jenis = str(row.get('JENIS', '')).strip().upper()
                    if code:
                        sku_decoder[code] = {"arti": arti, "Jenis": jenis}
            return sku_decoder
        except Exception as e:
            st.error(
                f"Gagal memuat Data Master SKU. Pastikan format file benar dan memiliki kolom 'CODE', 'ARTI', 'JENIS'. Error: {e}")
            return {}
    return {}


@st.cache_data
def load_data(file_uploader, file_type):
    """
    Fungsi umum untuk memuat data dari file Excel yang diunggah.
    """
    if file_uploader is not None:
        try:
            df = pd.read_excel(file_uploader)
            df.columns = [re.sub(r'\s+', ' ', col).strip() for col in df.columns]

            if file_type == "sales":
                df = df.rename(columns={
                    'SK U': 'SKU',
                    'Nama Toka Ziel Kids Officia Shop': 'Nama Toko',
                    'Salesmen': 'Salesman'
                })
                # Konversi Tanggal dengan format eksplisit dan errors='coerce'
                df['Tanggal'] = pd.to_datetime(df['Tanggal'], format='%d/%m/%Y %H:%M', errors='coerce')

                # Menggunakan errors='ignore' untuk pd.to_numeric, lalu astype(float) dan fillna(0)
                # untuk memastikan kolom numerik dan menangani nilai yang tidak dapat di-parse
                for col in ['QTY', 'Harga', 'Sub Total', 'Nett Sales']:
                    df[col] = pd.to_numeric(df[col], errors='ignore').astype(float).fillna(0)

                # Membersihkan dan mengonversi kolom HPP dan Gross Profit
                # Asumsi format Indonesia: Rp 1.234.567,89 -> 1234567.89
                df['HPP'] = df['HPP'].astype(str).str.replace('Rp', '', regex=False).str.replace('.', '',
                                                                                                 regex=False).str.replace(
                    ',', '.', regex=False).astype(float).fillna(0)
                df['Gross Profit'] = df['Gross Profit'].astype(str).str.replace('Rp', '', regex=False).str.replace('.',
                                                                                                                   '',
                                                                                                                   regex=False).str.replace(
                    ',', '.', regex=False).astype(float).fillna(0)
                return df
            elif file_type == "inbound":
                df = df.rename(columns={
                    'purchaseorder_no': 'No PO',
                    'supplier_name': 'Nama Supplier',
                    'Qty Dipesan': 'Qty Dipesan Unit',
                    'bill_no': 'No Bill',
                    'Catatan': 'Catatan',
                    'Pajak.1': 'Pajak Total',
                    'amount': 'Amount'
                })
                if 'Tanggal' not in df.columns:
                    raise KeyError(
                        "Kolom 'Tanggal' tidak ditemukan setelah pembersihan dan penamaan ulang di Data Inbound.")
                df['Tanggal'] = pd.to_datetime(df['Tanggal'],
                                               errors='coerce')  # Biarkan pandas infer format jika memungkinkan

                # Menggunakan errors='ignore' untuk pd.to_numeric, lalu astype(float) dan fillna(0)
                for col in ['Qty Dipesan Unit', 'Qty Diterima', 'Harga', 'Amount', 'Sub Total', 'Diskon', 'Pajak Total',
                            'Grand Total']:
                    # Menggunakan regex=False untuk str.replace jika tidak ada pola regex yang kompleks
                    df[col] = pd.to_numeric(df[col].astype(str).str.replace(' Buah', '', regex=False),
                                            errors='ignore').astype(float).fillna(0)

                return df
            elif file_type == "stock":
                df = df.rename(columns={
                    'Nama': 'Nama Item',
                    'is_bundle': 'Is Bundle'
                })
                # Menggunakan errors='ignore' untuk pd.to_numeric, lalu astype(float) dan fillna(0)
                for col in ['QTY', 'Dipesan', 'Tersedia', 'Harga Jual', 'HPP', 'Nilai Persediaan']:
                    df[col] = pd.to_numeric(df[col], errors='ignore').astype(float).fillna(0)
                return df
        except Exception as e:
            st.error(f"Gagal memuat file {file_type}. Pastikan format file benar. Error: {e}")
            return pd.DataFrame()
    return pd.DataFrame()


# --- Fungsi untuk Memparse SKU ---
def parse_sku(sku, sku_decoder):
    """
    Memparse string SKU untuk mengekstrak informasi kategori, tahun, musim, dll.
    Pola regex ini perlu disesuaikan dengan variasi format SKU Anda.
    Contoh format SKU yang diberikan: ZOZA21BAS-MIA-TBW35, Z11822BAS LUNA-BWT03, 201A21BAS-CND-ORG02, 202D24BAS-HTR-BLK01
    """
    sku_info = {
        "Original SKU": sku,
        "Category": "Unknown Category",
        "Sub Category": "Unknown Sub Category",
        "Tahun Produksi": "Unknown Tahun",
        "Season": "Unknown Musim",
        "Singkatan Nama Produk": "Unknown Produk",
        "Warna Produk": "Unknown Warna",
        "Size Produk": "Unknown Ukuran"
    }

    # Pola regex yang lebih fleksibel untuk menangani variasi SKU
    # Captures:
    # 1: First alphanumeric block (e.g., ZOZA, Z118, 201A, 202D, Z01)
    # 2: Optional second alphanumeric block (e.g., 118, A, D - if the first part was just 'Z', '201', '202')
    # 3: Year code (2 digits)
    # 4: Season code (3 letters)
    # 5: Product name code (any letters)
    # 6: Color code (3 letters)
    # 7: Size code (2 digits)
    match = re.match(r'([A-Z0-9]+)([A-Z0-9]+)?([0-9]{2})([A-Z]{3})[- ]([A-Z]+)-([A-Z]{3})([0-9]{2})', sku,
                     re.IGNORECASE)

    if match:
        parts = match.groups()
        first_code_part = parts[0].upper()
        second_code_part = parts[1].upper() if parts[1] else None
        year_code = parts[2]
        season_code = parts[3].upper()
        product_name_code = parts[4].upper()
        color_code = parts[5].upper()
        size_code = parts[6]

        # --- Logika untuk Kategori dan Sub Kategori ---
        if first_code_part in sku_decoder and sku_decoder[first_code_part]["Jenis"] == "CATEGORY":
            sku_info["Category"] = sku_decoder[first_code_part]["arti"]
        elif second_code_part and second_code_part in sku_decoder and sku_decoder[second_code_part][
            "Jenis"] == "CATEGORY":
            sku_info["Category"] = sku_decoder[second_code_part]["arti"]

        if first_code_part in sku_decoder and sku_decoder[first_code_part]["Jenis"] == "SUB CATEGORY":
            sku_info["Sub Category"] = sku_decoder[first_code_part]["arti"]
        elif second_code_part and second_code_part in sku_decoder and sku_decoder[second_code_part][
            "Jenis"] == "SUB CATEGORY":
            sku_info["Sub Category"] = sku_decoder[second_code_part]["arti"]

        # --- Logika untuk atribut lainnya ---
        sku_info["Tahun Produksi"] = sku_decoder.get(year_code, {}).get("arti", "Unknown Tahun")
        sku_info["Season"] = sku_decoder.get(season_code, {}).get("arti", "Unknown Musim")
        sku_info["Singkatan Nama Produk"] = sku_decoder.get(product_name_code, {}).get("arti", "Unknown Produk")
        sku_info["Warna Produk"] = sku_decoder.get(color_code, {}).get("arti", "Unknown Warna")
        sku_info["Size Produk"] = sku_decoder.get(size_code, {}).get("arti", "Unknown Ukuran")

    return sku_info


# --- Sidebar untuk Unggah File ---
st.sidebar.header("Unggah Data Bisnis Anda")
st.sidebar.markdown("Unggah file Excel Anda untuk memulai analisis.")

uploaded_sku_master_file = st.sidebar.file_uploader("1. Unggah Data Master SKU (Excel)", type=["xlsx", "xls"],
                                                    key="sku_master_uploader")
uploaded_sales_file = st.sidebar.file_uploader("2. Unggah Data Penjualan (Excel)", type=["xlsx", "xls"],
                                               key="sales_uploader")
uploaded_inbound_file = st.sidebar.file_uploader("3. Unggah Data Inbound Barang (Excel)", type=["xlsx", "xls"],
                                                 key="inbound_uploader")
uploaded_stock_file = st.sidebar.file_uploader("4. Unggah Data Stok Barang (Excel)", type=["xlsx", "xls"],
                                               key="stock_uploader")

# Inisialisasi state sesi untuk DataFrame
if 'df_sales_combined' not in st.session_state:
    st.session_state['df_sales_combined'] = pd.DataFrame()
if 'df_inbound_combined' not in st.session_state:
    st.session_state['df_inbound_combined'] = pd.DataFrame()
if 'df_stock_combined' not in st.session_state:
    st.session_state['df_stock_combined'] = pd.DataFrame()
if 'sku_decoder' not in st.session_state:
    st.session_state['sku_decoder'] = {}

# Proses unggah file SKU Master
if uploaded_sku_master_file:
    st.session_state['sku_decoder'] = load_sku_master(uploaded_sku_master_file)
    if not st.session_state['sku_decoder']:
        st.sidebar.error("Data Master SKU kosong atau gagal dimuat. Pastikan file benar.")
else:
    st.session_state['sku_decoder'] = {}

# Proses unggah file penjualan
if uploaded_sales_file and st.session_state['sku_decoder']:
    df_sales = load_data(uploaded_sales_file, "sales")
    if not df_sales.empty:
        if 'SKU' in df_sales.columns:
            df_sales_parsed_list = []
            for sku in df_sales['SKU'].astype(str):
                df_sales_parsed_list.append(parse_sku(sku, st.session_state['sku_decoder']))
            df_sales_parsed = pd.DataFrame(df_sales_parsed_list)
            st.session_state['df_sales_combined'] = pd.concat([df_sales, df_sales_parsed], axis=1)
        else:
            st.sidebar.warning("Kolom 'SKU' tidak ditemukan di Data Penjualan. Parsing SKU dilewati.")
            st.session_state['df_sales_combined'] = df_sales
    else:
        st.sidebar.error("Gagal memuat Data Penjualan. Pastikan format file benar.")
elif uploaded_sales_file and not st.session_state['sku_decoder']:
    st.sidebar.warning("Unggah Data Master SKU terlebih dahulu untuk parsing SKU pada Data Penjualan.")
    st.session_state['df_sales_combined'] = load_data(uploaded_sales_file, "sales")

# Proses unggah file inbound
if uploaded_inbound_file and st.session_state['sku_decoder']:
    df_inbound = load_data(uploaded_inbound_file, "inbound")
    if not df_inbound.empty:
        if 'SKU' in df_inbound.columns:
            df_inbound_parsed_list = []
            for sku in df_inbound['SKU'].astype(str):
                df_inbound_parsed_list.append(parse_sku(sku, st.session_state['sku_decoder']))
            df_inbound_parsed = pd.DataFrame(df_inbound_parsed_list)
            st.session_state['df_inbound_combined'] = pd.concat([df_inbound, df_inbound_parsed], axis=1)
        else:
            st.sidebar.warning("Kolom 'SKU' tidak ditemukan di Data Inbound. Parsing SKU dilewati.")
            st.session_state['df_inbound_combined'] = df_inbound
    else:
        st.sidebar.error("Gagal memuat Data Inbound. Pastikan format file benar.")
elif uploaded_inbound_file and not st.session_state['sku_decoder']:
    st.sidebar.warning("Unggah Data Master SKU terlebih dahulu untuk parsing SKU pada Data Inbound.")
    st.session_state['df_inbound_combined'] = load_data(uploaded_inbound_file, "inbound")

# Proses unggah file stok
if uploaded_stock_file and st.session_state['sku_decoder']:
    df_stock = load_data(uploaded_stock_file, "stock")
    if not df_stock.empty:
        if 'SKU' in df_stock.columns:
            df_stock_parsed_list = []
            for sku in df_stock['SKU'].astype(str):
                df_stock_parsed_list.append(parse_sku(sku, st.session_state['sku_decoder']))
            df_stock_parsed = pd.DataFrame(df_stock_parsed_list)
            st.session_state['df_stock_combined'] = pd.concat([df_stock, df_stock_parsed], axis=1)
        else:
            st.sidebar.warning("Kolom 'SKU' tidak ditemukan di Data Stok. Parsing SKU dilewati.")
            st.session_state['df_stock_combined'] = df_stock
    else:
        st.sidebar.error("Gagal memuat Data Stok. Pastikan format file benar.")
elif uploaded_stock_file and not st.session_state['sku_decoder']:
    st.sidebar.warning("Unggah Data Master SKU terlebih dahulu untuk parsing SKU pada Data Stok.")
    st.session_state['df_stock_combined'] = load_data(uploaded_stock_file, "stock")

# --- Dashboard Utama ---
st.title("Dashboard Analisis Data Bisnis")
st.markdown(
    "Dashboard ini membantu Anda menganalisis data penjualan, inbound, dan stok untuk mendapatkan wawasan bisnis.")

# Tampilkan dashboard hanya jika semua file telah diunggah dan tidak kosong
if not st.session_state['df_sales_combined'].empty and \
        not st.session_state['df_inbound_combined'].empty and \
        not st.session_state['df_stock_combined'].empty and \
        st.session_state['sku_decoder']:

    # --- Filter Interaktif ---
    st.sidebar.markdown("---")
    st.sidebar.header("Filter Data")

    df_sales_filtered = st.session_state['df_sales_combined'].copy()
    df_stock_filtered = st.session_state['df_stock_combined'].copy()
    df_inbound_filtered = st.session_state['df_inbound_combined'].copy()

    # Filter Tanggal Penjualan
    min_date = df_sales_filtered['Tanggal'].min().date() if not df_sales_filtered[
        'Tanggal'].empty else pd.Timestamp.now().date()
    max_date = df_sales_filtered['Tanggal'].max().date() if not df_sales_filtered[
        'Tanggal'].empty else pd.Timestamp.now().date()

    date_range = st.sidebar.date_input(
        "Pilih Rentang Tanggal Penjualan",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )

    if len(date_range) == 2:
        start_date = pd.to_datetime(date_range[0])
        end_date = pd.to_datetime(date_range[1])
        df_sales_filtered = df_sales_filtered[
            (df_sales_filtered['Tanggal'] >= start_date) & (df_sales_filtered['Tanggal'] <= end_date)]

    # Filter Kategori Produk
    all_categories = ['Semua Kategori'] + list(st.session_state['df_sales_combined']['Category'].unique())
    selected_categories = st.sidebar.multiselect("Filter Berdasarkan Kategori", all_categories,
                                                 default='Semua Kategori')

    if 'Semua Kategori' not in selected_categories:
        df_sales_filtered = df_sales_filtered[df_sales_filtered['Category'].isin(selected_categories)]
        df_stock_filtered = df_stock_filtered[df_stock_filtered['Category'].isin(selected_categories)]
        df_inbound_filtered = df_inbound_filtered[df_inbound_filtered['Category'].isin(selected_categories)]

    st.header("Ringkasan Kinerja Utama")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
        <div style="background-color:#F0F2F6; padding: 15px; border-radius: 10px; text-align: center; box-shadow: 2px 2px 5px rgba(0,0,0,0.1);">
            <h3 style="color:#303030; margin-bottom: 5px;">Total Penjualan</h3>
            <p style="font-size: 2em; color:#4CAF50; font-weight: bold;">Rp {df_sales_filtered['Nett Sales'].sum():,.2f}</p>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div style="background-color:#F0F2F6; padding: 15px; border-radius: 10px; text-align: center; box-shadow: 2px 2px 5px rgba(0,0,0,0.1);">
            <h3 style="color:#303030; margin-bottom: 5px;">Total Gross Profit</h3>
            <p style="font-size: 2em; color:#2196F3; font-weight: bold;">Rp {df_sales_filtered['Gross Profit'].sum():,.2f}</p>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div style="background-color:#F0F2F6; padding: 15px; border-radius: 10px; text-align: center; box-shadow: 2px 2px 5px rgba(0,0,0,0.1);">
            <h3 style="color:#303030; margin-bottom: 5px;">Total QTY Terjual</h3>
            <p style="font-size: 2em; color:#FF9800; font-weight: bold;">{df_sales_filtered['QTY'].sum():,.0f} unit</p>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        # Menghitung Inventory Turnover Ratio (sederhana: Total QTY Terjual / Rata-rata Stok Tersedia)
        # Ini adalah perhitungan snapshot, untuk akurasi lebih baik butuh data stok time-series
        avg_stock_qty = df_stock_filtered['Tersedia'].mean() if not df_stock_filtered.empty else 0
        inventory_turnover = (df_sales_filtered['QTY'].sum() / avg_stock_qty) if avg_stock_qty > 0 else 0
        st.markdown(f"""
        <div style="background-color:#F0F2F6; padding: 15px; border-radius: 10px; text-align: center; box-shadow: 2px 2px 5px rgba(0,0,0,0.1);">
            <h3 style="color:#303030; margin-bottom: 5px;">Perputaran Stok</h3>
            <p style="font-size: 2em; color:#9C27B0; font-weight: bold;">{inventory_turnover:,.2f}x</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # --- Analisis Penjualan ---
    st.header("Analisis Penjualan")

    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "Berdasarkan Kategori", "Berdasarkan Sub Kategori", "Berdasarkan Tahun Produksi",
        "Berdasarkan Musim", "Berdasarkan Warna", "Berdasarkan Ukuran", "Analisis Profitabilitas"
    ])

    with tab1:
        st.subheader("Penjualan Berdasarkan Kategori Produk")
        sales_by_category = df_sales_filtered.groupby('Category')['Sub Total'].sum().sort_values(
            ascending=False).reset_index()
        fig_sales_category = px.bar(sales_by_category, x='Category', y='Sub Total',
                                    title='Total Penjualan per Kategori',
                                    labels={'Sub Total': 'Total Penjualan (Rp)'},
                                    color='Category',
                                    template='plotly_white')
        st.plotly_chart(fig_sales_category, use_container_width=True)

    with tab2:
        st.subheader("Penjualan Berdasarkan Sub Kategori Produk")
        sales_by_subcategory = df_sales_filtered.groupby('Sub Category')['Sub Total'].sum().sort_values(
            ascending=False).reset_index()
        fig_sales_subcategory = px.bar(sales_by_subcategory, x='Sub Category', y='Sub Total',
                                       title='Total Penjualan per Sub Kategori',
                                       labels={'Sub Total': 'Total Penjualan (Rp)'},
                                       color='Sub Category',
                                       template='plotly_white')
        st.plotly_chart(fig_sales_subcategory, use_container_width=True)

    with tab3:
        st.subheader("Penjualan Berdasarkan Tahun Produksi")
        sales_by_year = df_sales_filtered.groupby('Tahun Produksi')['Sub Total'].sum().sort_values(
            ascending=False).reset_index()
        fig_sales_year = px.bar(sales_by_year, x='Tahun Produksi', y='Sub Total',
                                title='Total Penjualan per Tahun Produksi',
                                labels={'Sub Total': 'Total Penjualan (Rp)'},
                                color='Tahun Produksi',
                                template='plotly_white')
        st.plotly_chart(fig_sales_year, use_container_width=True)

    with tab4:
        st.subheader("Penjualan Berdasarkan Musim")
        sales_by_season = df_sales_filtered.groupby('Season')['Sub Total'].sum().sort_values(
            ascending=False).reset_index()
        fig_sales_season = px.bar(sales_by_season, x='Season', y='Sub Total',
                                  title='Total Penjualan per Musim',
                                  labels={'Sub Total': 'Total Penjualan (Rp)'},
                                  color='Season',
                                  template='plotly_white')
        st.plotly_chart(fig_sales_season, use_container_width=True)

    with tab5:
        st.subheader("Penjualan Berdasarkan Warna Produk")
        sales_by_color = df_sales_filtered.groupby('Warna Produk')['Sub Total'].sum().sort_values(
            ascending=False).reset_index()
        fig_sales_color = px.bar(sales_by_color, x='Warna Produk', y='Sub Total',
                                 title='Total Penjualan per Warna Produk',
                                 labels={'Sub Total': 'Total Penjualan (Rp)'},
                                 color='Warna Produk',
                                 template='plotly_white')
        st.plotly_chart(fig_sales_color, use_container_width=True)

    with tab6:
        st.subheader("Penjualan Berdasarkan Ukuran Produk")
        sales_by_size = df_sales_filtered.groupby('Size Produk')['Sub Total'].sum().sort_values(
            ascending=False).reset_index()
        fig_sales_size = px.bar(sales_by_size, x='Size Produk', y='Sub Total',
                                title='Total Penjualan per Ukuran Produk',
                                labels={'Sub Total': 'Total Penjualan (Rp)'},
                                color='Size Produk',
                                template='plotly_white')
        st.plotly_chart(fig_sales_size, use_container_width=True)

    with tab7:
        st.subheader("Analisis Profitabilitas Berdasarkan Kategori")
        profit_by_category = df_sales_filtered.groupby('Category')['Gross Profit'].sum().sort_values(
            ascending=False).reset_index()
        fig_profit_category = px.bar(profit_by_category, x='Category', y='Gross Profit',
                                     title='Total Gross Profit per Kategori',
                                     labels={'Gross Profit': 'Gross Profit (Rp)'},
                                     color='Category',
                                     template='plotly_white')
        st.plotly_chart(fig_profit_category, use_container_width=True)

        st.subheader("Analisis Profitabilitas Berdasarkan Sub Kategori")
        profit_by_subcategory = df_sales_filtered.groupby('Sub Category')['Gross Profit'].sum().sort_values(
            ascending=False).reset_index()
        fig_profit_subcategory = px.bar(profit_by_subcategory, x='Sub Category', y='Gross Profit',
                                        title='Total Gross Profit per Sub Kategori',
                                        labels={'Gross Profit': 'Gross Profit (Rp)'},
                                        color='Sub Category',
                                        template='plotly_white')
        st.plotly_chart(fig_profit_subcategory, use_container_width=True)

    st.subheader("Penjualan Berdasarkan Channel")
    sales_by_channel = df_sales_filtered.groupby('Channel')['Sub Total'].sum().sort_values(
        ascending=False).reset_index()
    fig_sales_channel = px.pie(sales_by_channel, names='Channel', values='Sub Total',
                               title='Proporsi Penjualan per Channel',
                               template='plotly_white')
    st.plotly_chart(fig_sales_channel, use_container_width=True)

    st.subheader("Top 10 Produk Terlaris (Berdasarkan QTY)")
    top_selling_products_qty = df_sales_filtered.groupby('Nama Barang')['QTY'].sum().sort_values(ascending=False).head(
        10).reset_index()
    fig_top_products_qty = px.bar(top_selling_products_qty, x='Nama Barang', y='QTY',
                                  title='Top 10 Produk Terlaris (QTY)',
                                  labels={'QTY': 'Jumlah Terjual (Unit)'},
                                  color='QTY',
                                  template='plotly_white')
    st.plotly_chart(fig_top_products_qty, use_container_width=True)

    st.subheader("Tren Penjualan Bulanan")
    df_sales_filtered['Bulan'] = df_sales_filtered['Tanggal'].dt.to_period('M').astype(str)
    monthly_sales = df_sales_filtered.groupby('Bulan')['Nett Sales'].sum().reset_index()
    fig_monthly_sales = px.line(monthly_sales, x='Bulan', y='Nett Sales',
                                title='Tren Penjualan Bersih Bulanan',
                                labels={'Nett Sales': 'Nett Sales (Rp)'},
                                markers=True,
                                template='plotly_white')
    st.plotly_chart(fig_monthly_sales, use_container_width=True)

    st.markdown("---")

    # --- Analisis Stok dan Inbound ---
    st.header("Analisis Stok dan Inbound")

    st.subheader("Ringkasan Stok Saat Ini")
    st.dataframe(df_stock_filtered[
                     ['Nama Item', 'Category', 'Sub Category', 'Lokasi', 'QTY', 'Tersedia', 'Harga Jual', 'HPP',
                      'Nilai Persediaan']])

    st.subheader("Perbandingan Stok Tersedia vs. Barang Diterima (Inbound)")
    inbound_by_sku = df_inbound_filtered.groupby('SKU')['Qty Diterima'].sum().reset_index(name='Total Qty Diterima')
    stock_available = df_stock_filtered.groupby('SKU')['Tersedia'].sum().reset_index(name='Total Tersedia')

    comparison_df = pd.merge(stock_available, inbound_by_sku, on='SKU', how='outer').fillna(0)
    comparison_df = pd.merge(comparison_df, df_stock_filtered[['SKU', 'Nama Item', 'Category']].drop_duplicates(),
                             on='SKU', how='left')
    comparison_df['Nama Item'] = comparison_df['Nama Item'].fillna(comparison_df['SKU'])

    fig_stock_inbound_comp = px.bar(comparison_df.sort_values(by='Total Tersedia', ascending=False).head(20),
                                    x='Nama Item', y=['Total Tersedia', 'Total Qty Diterima'],
                                    title='Stok Tersedia vs. Qty Diterima per SKU (Top 20)',
                                    labels={'value': 'Jumlah', 'variable': 'Tipe'},
                                    barmode='group',
                                    template='plotly_white')
    st.plotly_chart(fig_stock_inbound_comp, use_container_width=True)

    st.subheader("Distribusi Stok Berdasarkan Lokasi")
    stock_by_location = df_stock_filtered.groupby('Lokasi')['QTY'].sum().sort_values(ascending=False).reset_index()
    fig_stock_location = px.pie(stock_by_location, names='Lokasi', values='QTY',
                                title='Distribusi Stok Berdasarkan Lokasi',
                                template='plotly_white')
    st.plotly_chart(fig_stock_location, use_container_width=True)

    st.markdown("---")

    # --- Analisis Gabungan dan Masukan ---
    st.header("Analisis Gabungan dan Masukan")

    st.subheader("Rekomendasi Berdasarkan Data")

    st.write("**Produk dengan Stok Rendah dan Penjualan Tinggi:**")
    avg_sales_qty = df_sales_filtered['QTY'].mean()
    sales_agg = df_sales_filtered.groupby('SKU')['QTY'].sum().reset_index(name='TotalQTYTerjual')
    stock_agg = df_stock_filtered.groupby('SKU')['Tersedia'].sum().reset_index(name='TotalTersedia')

    merged_performance = pd.merge(sales_agg, stock_agg, on='SKU', how='left').fillna(0)
    low_stock_high_sales = merged_performance[
        (merged_performance['TotalTersedia'] < 50) &
        (merged_performance['TotalQTYTerjual'] > avg_sales_qty)
        ]
    if not low_stock_high_sales.empty:
        low_stock_high_sales = pd.merge(low_stock_high_sales,
                                        df_stock_filtered[['SKU', 'Nama Item', 'Category']].drop_duplicates(), on='SKU',
                                        how='left')
        st.dataframe(low_stock_high_sales[['Nama Item', 'Category', 'TotalQTYTerjual', 'TotalTersedia']])
        st.info(
            "Rekomendasi: Pertimbangkan untuk melakukan pemesanan ulang segera untuk produk-produk ini untuk menghindari kehabisan stok dan kehilangan potensi penjualan.")
    else:
        st.info("Tidak ada produk dengan stok rendah dan penjualan tinggi yang teridentifikasi saat ini.")

    st.write("**Produk dengan Stok Berlebih:**")
    high_stock_low_sales = merged_performance[
        (merged_performance['TotalTersedia'] > 100) &
        (merged_performance['TotalQTYTerjual'] < avg_sales_qty)
        ]
    if not high_stock_low_sales.empty:
        high_stock_low_sales = pd.merge(high_stock_low_sales,
                                        df_stock_filtered[['SKU', 'Nama Item', 'Category']].drop_duplicates(), on='SKU',
                                        how='left')
        st.dataframe(high_stock_low_sales[['Nama Item', 'Category', 'TotalQTYTerjual', 'TotalTersedia']])
        st.info(
            "Rekomendasi: Pertimbangkan strategi promosi, diskon, atau penjualan cepat untuk produk-produk ini guna mengurangi biaya penyimpanan dan membebaskan modal.")
    else:
        st.info("Tidak ada produk dengan stok berlebih yang teridentifikasi saat ini.")

    st.markdown("---")
    st.subheader("Tabel Data Mentah (untuk Pemeriksaan Detail)")
    with st.expander("Lihat Data Penjualan Lengkap"):
        st.dataframe(df_sales_filtered)
    with st.expander("Lihat Data Inbound Barang Lengkap"):
        st.dataframe(df_inbound_filtered)
    with st.expander("Lihat Data Stok Barang Lengkap"):
        st.dataframe(df_stock_filtered)

else:
    st.info(
        "Mohon unggah semua file data (Data Master SKU, Penjualan, Inbound, dan Stok) melalui sidebar untuk memulai analisis dan menampilkan dashboard.")
    st.markdown("""
    **Petunjuk:**
    1. **Unggah Data Master SKU terlebih dahulu.** File ini harus memiliki kolom 'CODE', 'ARTI', dan 'JENIS'.
    2. Kemudian, klik tombol "Browse files" di sidebar untuk setiap jenis data lainnya (Penjualan, Inbound, Stok).
    3. Pastikan file Anda dalam format Excel (.xlsx atau .xls).
    4. Setelah semua file diunggah, dashboard akan otomatis muncul.
    """)
