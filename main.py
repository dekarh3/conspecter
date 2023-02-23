import kivy
kivy.require('1.9.1')

import os
import xmltodict
import sqlite3
from kivy.app import App
from kivy.factory import Factory
from kivy.uix.widget import Widget
from kivy.properties import ObjectProperty, StringProperty, NumericProperty, ColorProperty
from kivy.uix.treeview import TreeView, TreeViewLabel
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.popup import Popup
from kivy.utils import platform
if platform == 'android':
    from android.permissions import request_permissions, Permission
    from android.storage import primary_external_storage_path
    request_permissions([Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE]) # Даём разрешение на чтение и запись (в моём случае)
    DIR = os.path.join(primary_external_storage_path(), 'mytetra')
    APP_PATH = os.path.dirname(os.path.abspath(__file__))
else:
    DIR = ''
    APP_PATH = ''
CREATE_DB = False


class MyFileChooserListView(FileChooserListView):
    startpath = DIR

class MyTreeViewLabel(TreeViewLabel):
    external_id = NumericProperty(0)

class MyTreeView(TreeView):
    def __init__(self, **kwargs):
        super(MyTreeView, self).__init__(**kwargs)
        #self.main_dir_path = DIR
        #with open(os.path.join(self.main_dir_path, 'mytetra.xml'), 'r') as read_file:
        #    main_file = read_file.read()        
        #self.main_tree = xmltodict.parse(main_file)
        self.uid2id = {}
        self.nodes = {}
        self.populate_tree_view(None, 0)#, self.main_tree['root']['content'])

    def populate_tree_view(self, parent, node_id):
        if parent is None:
            tree_node = self.add_node(MyTreeViewLabel(text='', is_open=True, external_id=0))
            self.uid2id[tree_node.uid] = 0
            self.nodes[0] = tree_node
        else:
            cur.execute('SELECT id, name FROM tags WHERE id = ?;', (node_id,))
            request = cur.fetchone()
            tree_node = self.add_node(MyTreeViewLabel(text=request[1], is_open=True,
                                                           external_id=request[0]), parent)
            self.uid2id[tree_node.uid] = request[0]
            self.nodes[request[0]] = tree_node
        cur.execute('SELECT id, name FROM tags WHERE parent = ?;', (node_id,))
        request = cur.fetchall()
        for child_node in request:
            self.populate_tree_view(tree_node, child_node[0])
    def depopulate_tree_view(self):
        for node in self.nodes:
            self.remove_node(self.nodes[node])
        self.nodes = {}
        self.node_ids = {}
    def reload_tree(self, main_dir_path):
        #with open(os.path.join(main_dir_path, 'mytetra.xml'), 'r') as read_file:
        #    main_file = read_file.read()
        #self.main_tree = xmltodict.parse(main_file)
        self.depopulate_tree_view()
        self.populate_tree_view(None) #, self.main_tree['root']['content'])
    def delete_node(self, node_id):
        cur.execute('DELETE FROM tags WHERE id = ?;', (node_id,))
        conn.commit()
        self.reload_tree()
    def child_list(self, node_id):
        node_ids = []
        for node in self.iterate_all_nodes(self.nodes[node_id]):
            node_ids.append(self.uid2id[node.uid])
        return node_ids

class MyBoxLayout(BoxLayout):
    background_color = ColorProperty() # The ListProperty will also work.


class LoadDialog(FloatLayout):
    loaddb = ObjectProperty(None)
    cancel = ObjectProperty(None)


class MyGrid(Widget):
    tag = ObjectProperty(None)
    mention = ObjectProperty(None)
    def __init__(self, **kwargs):
        super(MyGrid, self).__init__(**kwargs)
        self.tvedit_regim = 'Добавление'
        self.tvedit_current_id = 0
        self.tvedit_captured_id = -1
    def btn_tvedit_change_click(self):
        '''Переключение режимов редактирования дерева'''
        if self.tvedit_regim == 'Добавление':
            self.tvedit_regim = 'Редактирование'
            self.ids.btn_tvedit_change.text = self.tvedit_regim
            self.ids.btn_tvedit_minus.disabled = True
            self.ids.btn_tvedit_minus.text = ''
            self.ids.btn_tvedit_plus.disabled = True
            self.ids.btn_tvedit_plus.text = 'ok'
            self.ids.tvedit_text.text = self.tag.nodes[self.tvedit_current_id].text
            self.ids.tvedit_text.readonly = False
        elif self.tvedit_regim == 'Редактирование':
            self.tvedit_regim = 'Удаление'
            self.ids.btn_tvedit_change.text = self.tvedit_regim
            self.ids.btn_tvedit_minus.disabled = True
            self.ids.btn_tvedit_minus.text = ''
            self.ids.btn_tvedit_plus.disabled = not self.tag.nodes[self.tvedit_current_id].is_leaf
            self.ids.btn_tvedit_plus.text = '-'
            self.ids.tvedit_text.text = self.tag.nodes[self.tvedit_current_id].text
            self.ids.tvedit_text.readonly = True
        elif self.tvedit_regim == 'Удаление':
            self.tvedit_regim = 'Перенос'
            self.ids.btn_tvedit_change.text = self.tvedit_regim
            self.ids.btn_tvedit_minus.disabled = False
            self.ids.btn_tvedit_minus.text = 'ok'
            self.ids.btn_tvedit_plus.disabled = True
            self.ids.btn_tvedit_plus.text = '>'
            self.ids.tvedit_text.text = ''
            self.ids.tvedit_text.readonly = True
        else:
            self.tvedit_regim = 'Добавление'
            self.ids.btn_tvedit_change.text = self.tvedit_regim
            self.ids.btn_tvedit_minus.disabled = True
            self.ids.btn_tvedit_minus.text = ''
            self.ids.btn_tvedit_plus.disabled = True
            self.ids.btn_tvedit_plus.text = '+'
            self.ids.tvedit_text.text = ''
            self.ids.tvedit_text.readonly = False

    def btn_tvedit_minus_click(self):
        if self.tvedit_regim == 'Перенос':
            if self.tvedit_captured_id < 0:
                self.tvedit_captured_id = self.tvedit_current_id
                self.ids.tvedit_text.text = self.tag.nodes[self.tvedit_current_id].text
                self.ids.btn_tvedit_minus.text = '<'
            else:
                self.ids.tvedit_text.text = ''
                self.ids.btn_tvedit_plus.disabled = True
                self.ids.btn_tvedit_minus.text = 'ok'
                self.ids.btn_tvedit_minus.disabled = False
                self.tvedit_captured_id = -1
    def btn_tvedit_plus_click(self):
        pass
    def tv_touch(self, value):
        self.tvedit_current_id = self.tag.uid2id[value]
        if self.tvedit_regim == 'Редактирование' or self.tvedit_regim == 'Удаление':
            self.ids.tvedit_text.text = self.tag.nodes[self.tvedit_current_id].text
        elif self.tvedit_regim == 'Перенос':
            if self.tvedit_current_id != self.tvedit_captured_id and self.tvedit_captured_id > -1 \
                    and self.tvedit_current_id not in self.tag.child_list(self.tvedit_captured_id):
                self.ids.btn_tvedit_plus.disabled = False
            else:
                self.ids.btn_tvedit_plus.disabled = True
        if self.tvedit_regim == 'Удаление':
            self.ids.btn_tvedit_plus.disabled = not self.tag.nodes[self.tvedit_current_id].is_leaf
    def spn_lecture_click(self, value):
        self.ids.file_id_time.text = value
        self.ids.transcript_text.text = f'You Selected: {value}'
    def btn_conspect_click(self, value):
        self.ids.file_id_time.text = value
        self.ids.transcript_text.text = f'You Selected: {value}'
    def cancel_dialog(self):
        self._popup.dismiss()
    def show_loaddb_dialog(self):
        content = LoadDialog(loaddb=self.loaddb, cancel=self.cancel_dialog)
        self._popup = Popup(title="Выбрать mytetra.xml", content=content,
                            size_hint=(0.9, 0.9))
        self._popup.open()
    def loaddb(self, path, filename):
        ''' Актуализировать импорт из db'''
        if os.path.basename(os.path.join(path, filename[0])) == 'mytetra.xml':
            main_dir_path = os.path.dirname(os.path.join(path, filename[0]))
            #self.tag.reload_tree(main_dir_path)
            q=0
        self.cancel_dialog()


class TrainerApp(App): # <- Main Class
    def build(self):
        return MyGrid()

if __name__ == "__main__":
    if CREATE_DB:                                       # Создание первичной структуры
        if os.path.exists(os.path.join(APP_PATH, 'main.db')):
            os.remove(os.path.join(APP_PATH, 'main.db'))
        conn = sqlite3.connect(os.path.join(APP_PATH, 'main.db'))
        cur = conn.cursor()
        cur.execute("""
            PRAGMA foreign_keys=on;""")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users(
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL);""")
        conn.commit()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tags(
                id INT PRIMARY KEY,
                parent INT NOT NULL,
                name TEXT NOT NULL,
                user_id TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id));""")
        conn.commit()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS audios(
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                author TEXT,
                created DATETIME,
                duration INT,
                transcription TEXT,
                user_id TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id));""")
        conn.commit()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS timestamps(
                second INT,
                name TEXT NOT NULL,
                author TEXT,
                created DATETIME,
                duration INT,
                user_id TEXT,
                audio_id INT,
                CONSTRAINT id PRIMARY KEY (second, audio_id),
                FOREIGN KEY (audio_id) REFERENCES audios(id),
                FOREIGN KEY (user_id) REFERENCES users(id));""")
        conn.commit()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pdfs(
                hash TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                title TEXT NOT NULL,                    
                author TEXT,
                created DATETIME,
                total_pages INT,
                user_id TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id));""")
        conn.commit()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS conspects(
                id INT PRIMARY KEY,                    
                hash TEXT,
                content TEXT NOT NULL,                    
                edited DATETIME,
                second REAL,
                page INT,
                tag_id INT,
                audio_id TEXT,
                pdf_id TEXT,
                user_id TEXT,
                FOREIGN KEY (tag_id) REFERENCES tag(id),
                FOREIGN KEY (audio_id) REFERENCES audios(id),
                FOREIGN KEY (pdf_id) REFERENCES pdfs(id),
                FOREIGN KEY (user_id) REFERENCES users(id));""")
        conn.commit()
        cur.executemany('INSERT INTO users VALUES(?, ?);', [('q1q1', 'Денис Алексеев')])
        conn.commit()
        cur.executemany('INSERT INTO tags VALUES(?, ?, ?, ?);', [(1, 0, 'юриспруденция', 'q1q1'),
                                                                 (2, 0, 'программирование', 'q1q1'),
                                                                 (3, 1, 'вексельное право', 'q1q1'),
                                                                 (4, 2, 'ELMA365','q1q1'),
                                                                 (5, 3, 'выгодоприобретатель','q1q1'),
                                                                 (6, 5, 'с оборотом','q1q1')])
        conn.commit()
        #conn.close()
    else:
        if os.path.exists(os.path.join(APP_PATH, 'main.db')):
            conn = sqlite3.connect(os.path.join(APP_PATH, 'main.db'))
            cur = conn.cursor()
    Factory.register('LoadDialog', cls=LoadDialog)
    TrainerApp().run()

