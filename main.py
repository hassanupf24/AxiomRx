import sys
import logging
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, QTabWidget,
    QPushButton, QTableWidget, QTableWidgetItem, QFileDialog, QMessageBox, QHeaderView,
    QHBoxLayout, QLineEdit, QFormLayout, QDateEdit, QDoubleSpinBox, QSpinBox
)
from PyQt6.QtCore import Qt, QDate

from database import initialize_database
import crud
import ocr
import forecasting

logging.basicConfig(level=logging.INFO)

class ProductsTab(QWidget):
    """إدارة الأدوية والمخزون - يدعم العمل دون اتصال"""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Form
        form_layout = QFormLayout()
        self.name_input = QLineEdit()
        self.barcode_input = QLineEdit()
        self.category_input = QLineEdit()
        self.qty_input = QSpinBox()
        self.qty_input.setMaximum(100000)
        self.reorder_input = QSpinBox()
        self.reorder_input.setMaximum(100000)
        self.expiry_input = QDateEdit()
        self.expiry_input.setDate(QDate.currentDate().addYears(1))
        self.expiry_input.setDisplayFormat("yyyy-MM-dd")
        self.price_input = QDoubleSpinBox()
        self.price_input.setMaximum(100000.0)
        
        form_layout.addRow("اسم الدواء:", self.name_input)
        form_layout.addRow("الباركود المرجعي:", self.barcode_input)
        form_layout.addRow("التصنيف:", self.category_input)
        form_layout.addRow("الكمية الحالية:", self.qty_input)
        form_layout.addRow("حد إعادة الطلب (رصيد الخطر):", self.reorder_input)
        form_layout.addRow("تاريخ الانتهاء:", self.expiry_input)
        form_layout.addRow("سعر البيع للمستهلك:", self.price_input)
        
        layout.addLayout(form_layout)
        
        self.add_btn = QPushButton("➕ إضافة دواء جديد للسجل المحلي")
        self.add_btn.setStyleSheet("padding: 8px; font-weight: bold; background-color: #2c3e50; color: white;")
        self.add_btn.clicked.connect(self.add_product)
        layout.addWidget(self.add_btn)
        
        # Table
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "الكود (ID)", "اسم الدواء", "الباركود", "التصنيف", "الكمية", "الصلاحية", "السعر"
        ])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        
        self.refresh_timer = QPushButton("🔄 تحديث قائمة المستودع")
        self.refresh_timer.clicked.connect(self.load_products)
        layout.addWidget(self.refresh_timer)
        
        self.load_products()

    def add_product(self):
        try:
            if not self.name_input.text() or not self.barcode_input.text():
                QMessageBox.warning(self, "خطأ بالبيانات", "يرجى ادخال الاسم والباركود!")
                return
                
            crud.add_product(
                self.name_input.text(),
                self.barcode_input.text(),
                self.category_input.text(),
                self.qty_input.value(),
                self.reorder_input.value(),
                self.expiry_input.date().toString("yyyy-MM-dd"),
                self.price_input.value()
            )
            QMessageBox.information(self, "تم بنجاح", "تم حفظ بيانات الدواء بالقاعدة المحلية.")
            self.load_products()
            
            # Clear fields
            self.name_input.clear()
            self.barcode_input.clear()
            self.category_input.clear()
            self.qty_input.setValue(0)
            self.price_input.setValue(0.0)
            
        except Exception as e:
            QMessageBox.critical(self, "فشل", f"تعذر الإضافة بسبب خطأ في قاعدة البيانات:\n{e}")

    def load_products(self):
        products = crud.get_all_products()
        self.table.setRowCount(0)
        for row_idx, p in enumerate(products):
            self.table.insertRow(row_idx)
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(p['ID'])))
            self.table.setItem(row_idx, 1, QTableWidgetItem(str(p['Name'])))
            self.table.setItem(row_idx, 2, QTableWidgetItem(str(p['Barcode'])))
            self.table.setItem(row_idx, 3, QTableWidgetItem(str(p['Category'])))
            self.table.setItem(row_idx, 4, QTableWidgetItem(str(p['StockQuantity'])))
            self.table.setItem(row_idx, 5, QTableWidgetItem(str(p['ExpiryDate'])))
            self.table.setItem(row_idx, 6, QTableWidgetItem(str(p['UnitPrice'])))


class POSTab(QWidget):
    """نقطة البيع (الكاشير) مع محرك الذكاء الاصطناعي لقراءة الروشتات"""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        
        top_layout = QHBoxLayout()
        self.barcode_input = QLineEdit()
        self.barcode_input.setPlaceholderText("قم بتمرير قارئ الباركود أو ادخال رقم الباركود هنا والضغط على Enter...")
        self.barcode_input.returnPressed.connect(self.search_barcode)
        top_layout.addWidget(self.barcode_input)
        
        self.upload_btn = QPushButton("📷 قراءة الروشتة ضوئياً (AI OCR)")
        self.upload_btn.setStyleSheet("padding: 10px; font-weight: bold; background-color: #2980b9; color: white;")
        self.upload_btn.clicked.connect(self.upload_prescription)
        top_layout.addWidget(self.upload_btn)
        
        layout.addLayout(top_layout)
        
        self.cart_table = QTableWidget(0, 4)
        self.cart_table.setHorizontalHeaderLabels(["الكود", "اسم الصنف", "الكمية", "الإجمالي"])
        self.cart_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.cart_table)
        
        bottom_layout = QHBoxLayout()
        self.total_label = QLabel("الإجمالي الكلي: 0.0")
        self.total_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #c0392b;")
        bottom_layout.addWidget(self.total_label)
        
        self.checkout_btn = QPushButton("💳 تسجيل وطباعة الفاتورة")
        self.checkout_btn.setStyleSheet("padding: 15px; font-size: 16px; background-color: #27ae60; color: white; font-weight: bold;")
        self.checkout_btn.clicked.connect(self.checkout)
        bottom_layout.addWidget(self.checkout_btn)
        
        layout.addLayout(bottom_layout)
        
        self.setLayout(layout)
        
        self.cart_items = []
        self.current_total = 0.0

    def search_barcode(self):
        barcode = self.barcode_input.text().strip()
        product = crud.get_product_by_barcode(barcode)
        if product:
            self.add_to_cart(product)
            self.barcode_input.clear()
        else:
            QMessageBox.warning(self, "غير موجود", "لا يوجد صنف مسجل بهذا الباركود!")
            self.barcode_input.selectAll()

    def upload_prescription(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "إدراج صورة روشتة طبيب", "", "Image Files (*.png *.jpg *.jpeg *.bmp)"
        )
        if file_name:
            try:
                products = crud.get_all_products()
                if not products:
                    QMessageBox.warning(self, "القاعدة فارغة", "يجب إضافة المنتجات إلى قاعدة البيانات أولاً قبل محاولة قراءة الروشتات.")
                    return
                    
                matched_products = ocr.process_prescription(file_name, products)
                if not matched_products:
                    QMessageBox.information(self, "النتيجة", "لم يتعرف الذكاء الاصطناعي على أي أصناف مطابقة من الروشتة في مستودعك.")
                
                for p in matched_products:
                    self.add_to_cart(p)
                    
            except Exception as e:
                QMessageBox.critical(self, "خطأ بالنظام", f"فشل تحليل الصورة:\n{e}")

    def add_to_cart(self, product):
        qty = 1
        subtotal = float(product['UnitPrice']) * qty
        
        # Check if already in cart
        found = False
        for item in self.cart_items:
            if item['product_id'] == product['ID']:
                item['quantity'] += 1
                item['subtotal'] += float(product['UnitPrice'])
                found = True
                break
                
        if not found:
            self.cart_items.append({
                'product_id': product['ID'], 
                'quantity': qty, 
                'subtotal': subtotal, 
                'name': product['Name']
            })
            
        self.refresh_cart_table()

    def refresh_cart_table(self):
        self.cart_table.setRowCount(0)
        self.current_total = 0.0
        
        for row_idx, item in enumerate(self.cart_items):
            self.cart_table.insertRow(row_idx)
            self.cart_table.setItem(row_idx, 0, QTableWidgetItem(str(item['product_id'])))
            self.cart_table.setItem(row_idx, 1, QTableWidgetItem(str(item['name'])))
            self.cart_table.setItem(row_idx, 2, QTableWidgetItem(str(item['quantity'])))
            self.cart_table.setItem(row_idx, 3, QTableWidgetItem(str(item['subtotal'])))
            self.current_total += item['subtotal']
            
        self.total_label.setText(f"الإجمالي الكلي: {self.current_total:.2f}")

    def checkout(self):
        if not self.cart_items:
            QMessageBox.warning(self, "فارغة", "القائمة فارغة، قم بإضافة دواء أولاً.")
            return
            
        try:
            crud.record_sale(self.current_total, "Cash", self.cart_items)
            QMessageBox.information(self, "اكتملت العملية", f"تم اعتماد البيع وخصم الكميات من المستودع.\nالإجمالي: {self.current_total:.2f}")
            self.cart_items = []
            self.refresh_cart_table()
        except Exception as e:
            QMessageBox.critical(self, "خطأ بالنظام", f"تعذر تسجيل المعاملة:\n{e}")


class InventoryTab(QWidget):
    """محرك التنبؤ والتحليل الذكي للنواقص"""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        
        self.forecast_btn = QPushButton("⚡ تحليل بيانات المبيعات وتوليد النواقص المتوقعة لـ 14 يوم (تنبؤ ذكي)")
        self.forecast_btn.setStyleSheet("padding: 12px; font-weight: bold; background-color: #8e44ad; color: white; font-size: 15px;")
        self.forecast_btn.clicked.connect(self.generate_forecast)
        layout.addWidget(self.forecast_btn)
        
        self.restock_table = QTableWidget(0, 6)
        self.restock_table.setHorizontalHeaderLabels([
            "م", "الصنف", "الرصيد الحالي", 
            "حد إعادة الطلب الآمن", "المنصرف المتوقع للتبنؤ", "النتيجة المستقبلية للمخزون"
        ])
        self.restock_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.restock_table)
        
        self.setLayout(layout)
        
    def generate_forecast(self):
        try:
            items = forecasting.generate_smart_restock_list(forecast_horizon_days=14)
            self.populate_table(items)
        except Exception as e:
            QMessageBox.critical(self, "فشل الذكاء الاصطناعي", f"تعذر استخراج تحليل التنبؤات:\nتأكد من وجود مبيعات سابقة كافية لتدريب الخوارزمية.\nتفاصيل:\n{e}")
            
    def populate_table(self, items):
        self.restock_table.setRowCount(0)
        for row_idx, item in enumerate(items):
            self.restock_table.insertRow(row_idx)
            self.restock_table.setItem(row_idx, 0, QTableWidgetItem(str(item['ProductID'])))
            self.restock_table.setItem(row_idx, 1, QTableWidgetItem(str(item['Name'])))
            self.restock_table.setItem(row_idx, 2, QTableWidgetItem(str(item['CurrentStock'])))
            self.restock_table.setItem(row_idx, 3, QTableWidgetItem(str(item['ReorderLevel'])))
            
            dem_item = QTableWidgetItem(str(item['PredictedDemand']))
            dem_item.setBackground(Qt.GlobalColor.darkYellow)
            self.restock_table.setItem(row_idx, 4, dem_item)
            
            projected = item['ProjectedStock']
            proj_item = QTableWidgetItem(f"{projected} (عجز)")
            if projected <= 0:
                proj_item.setForeground(Qt.GlobalColor.white)
                proj_item.setBackground(Qt.GlobalColor.darkRed)
            self.restock_table.setItem(row_idx, 5, proj_item)
            
        if not items:
            QMessageBox.information(self, "المستودع سليم", "خوارزمية الذكاء الاصطناعي لم تكتشف أي أدوية يُتوقع نفاذها في الـ 14 يوم القادمة.")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AxiomRx - نظام إدارة العيادات والصيدليات الشامل")
        
        # Enable Right-to-Left formatting for Arabic locale Windows usage
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft) 
        self.resize(1100, 750)
        
        tabs = QTabWidget()
        tabs.addTab(POSTab(), "🛒 الكاشير (نقطة البيع)")
        tabs.addTab(ProductsTab(), "📦 إدارة النواقص والأدوية")
        tabs.addTab(InventoryTab(), "🧠 التنبؤ الاصطناعي للمخزون")
        
        self.setCentralWidget(tabs)
        
        # Basic Modern Styling
        self.setStyleSheet("""
            QTabBar::tab { font-size: 16px; padding: 12px; font-weight: bold; }
            QPushButton { border-radius: 4px; border: 1px solid #bdc3c7; }
            QPushButton:hover { background-color: #ecf0f1; }
            QTableWidget { font-size: 14px; alternate-background-color: #f9f9f9; }
            QLineEdit, QSpinBox, QDoubleSpinBox, QDateEdit { padding: 8px; font-size: 14px; border: 1px solid #ccc; border-radius: 4px; }
        """)

def main():
    try:
        initialize_database()
        logging.info("Standalone Windows SQLite DB Initialized successfully.")
    except Exception as e:
        app = QApplication(sys.argv)
        QMessageBox.critical(None, "عطل بالنظام", f"حدث عطل في توليد قاعدة البيانات المحلية:\n{e}")
        sys.exit(1)
        
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    font = app.font()
    font.setFamily("Segoe UI")
    font.setPointSize(10)
    app.setFont(font)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
