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
        self.node_ids = {}
        self.nodes = []
        self.populate_tree_view(None, 0)#, self.main_tree['root']['content'])

    def populate_tree_view(self, parent, node):
        if parent is None:
            tree_node = self.add_node(MyTreeViewLabel(text='', is_open=True, external_id=0))
            self.node_ids[tree_node.uid] = 0
            self.nodes.append(tree_node)
        else:
            cur.execute('SELECT id, name FROM tags WHERE id = ?;', (node,))
            request = cur.fetchone()
            tree_node = self.add_node(MyTreeViewLabel(text=request[1], is_open=True,
                                                           external_id=request[0]), parent)
            self.node_ids[tree_node.uid] = request[0]
            self.nodes.append(tree_node)
        cur.execute('SELECT id, name FROM tags WHERE parent = ?;', (node,))
        request = cur.fetchall()
        for child_node in request:
            self.populate_tree_view(tree_node, child_node[0])

    def depopulate_tree_view(self):
        for node in self.nodes:
            self.remove_node(node)
        self.nodes = []
        self.node_ids = {}

    def reload_tree(self, main_dir_path):
        #with open(os.path.join(main_dir_path, 'mytetra.xml'), 'r') as read_file:
        #    main_file = read_file.read()
        #self.main_tree = xmltodict.parse(main_file)
        self.depopulate_tree_view()
        self.populate_tree_view(None) #, self.main_tree['root']['content'])


class MyBoxLayout(BoxLayout):
    background_color = ColorProperty() # The ListProperty will also work.


class LoadDialog(FloatLayout):
    load_mytetra = ObjectProperty(None)
    cancel = ObjectProperty(None)


class MyGrid(Widget):
    tag = ObjectProperty(None)
    mention = ObjectProperty(None)
    def dismiss_popup(self):
        self._popup.dismiss()
    def tv_touch(self, value):
        print(self.tag.node_ids[value])
    def spinner_clicked(self, value):
        self.ids.file_id_time.text = value
        self.ids.transcript_text.text = f'You Selected: {value}'
    def button_clicked(self, value):
        self.ids.file_id_time.text = value
        self.ids.transcript_text.text = f'You Selected: {value}'
    def show_load(self):
        content = LoadDialog(load_mytetra=self.load_mytetra, cancel=self.dismiss_popup)
        self._popup = Popup(title="Выбрать mytetra.xml", content=content,
                            size_hint=(0.9, 0.9))
        self._popup.open()
    def load_mytetra(self, path, filename):
        if os.path.basename(os.path.join(path, filename[0])) == 'mytetra.xml':
            main_dir_path = os.path.dirname(os.path.join(path, filename[0]))
            self.tag.reload_tree(main_dir_path)
            q=0
        self.dismiss_popup()


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
                                                                 (4, 2, 'ELMA365','q1q1')])
        conn.commit()
        conn.close()
    else:
        if os.path.exists(os.path.join(APP_PATH, 'main.db')):
            conn = sqlite3.connect(os.path.join(APP_PATH, 'main.db'))
            cur = conn.cursor()
    Factory.register('LoadDialog', cls=LoadDialog)
    TrainerApp().run()

