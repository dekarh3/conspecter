import kivy
kivy.require('1.9.1')

import os
import sqlite3
from datetime import datetime
import hashlib
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled
from kivy.app import App
from kivy.factory import Factory
from kivy.uix.widget import Widget
from kivy.properties import ObjectProperty, StringProperty, NumericProperty, ColorProperty
from kivy.uix.treeview import TreeView, TreeViewLabel
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.utils import platform
if platform == 'android':
    from android.permissions import request_permissions, Permission
    from android.storage import primary_external_storage_path
    request_permissions([Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE]) # Даём разрешение на чтение и запись (в моём случае)
    DIR = os.path.join(primary_external_storage_path())
    APP_PATH = os.path.dirname(os.path.abspath(__file__))
else:
    DIR = '.'
    APP_PATH = ''
CREATE_DB = False


class MyFileChooserListView(FileChooserListView):
    startpath = DIR


class MyTreeViewLabel(TreeViewLabel):
    external_id = NumericProperty(0)

    def label_touch(self, tvl, mouse):
        self.parent.parent.parent.parent.parent.parent.tv_touch(tvl.uid)


class MyButton(Button):
    ext_id = NumericProperty(0)

    def on_release(self):
        q=0


class MyTreeView(TreeView):
    def __init__(self, **kwargs):
        super(MyTreeView, self).__init__(**kwargs)
        self.uid2id = {}
        self.id2uid = {}
        self.nodes = {}
        self.populate_tree_view(None, 0)

    def populate_tree_view(self, parent, node_id):
        if parent is None:
            my_tree_view_label = MyTreeViewLabel(text='', is_open=True, external_id=0)
            my_tree_view_label.bind(on_touch_down=my_tree_view_label.label_touch)
            tree_node = self.add_node(my_tree_view_label)
            self.uid2id[tree_node.uid] = 0
            self.id2uid[0] = tree_node.uid
            self.nodes[0] = tree_node
        else:
            cur.execute('SELECT id, name FROM tags WHERE id = ?;', (node_id,))
            request = cur.fetchone()
            my_tree_view_label = MyTreeViewLabel(text=request[1], is_open=True, external_id=request[0])
            my_tree_view_label.bind(on_touch_down=my_tree_view_label.label_touch)
            tree_node = self.add_node(my_tree_view_label, parent)
            self.uid2id[tree_node.uid] = request[0]
            self.id2uid[request[0]] = tree_node.uid
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

    def reload_tree(self):
        self.depopulate_tree_view()
        self.populate_tree_view(None, 0)

    def delete_node(self, node_id):
        cur.execute('DELETE FROM tags WHERE id = ?;', (node_id,))
        conn.commit()
        self.reload_tree()

    def child_list(self, node_id):
        node_ids = []
        for node in self.iterate_all_nodes(self.nodes[node_id]):
            node_ids.append(self.uid2id[node.uid])
        return node_ids

    def parent_list(self, node_id):
        node_names = []
        while self.nodes[node_id].parent_node:
            node_names.append(self.nodes[node_id].text)
            if str(type(self.nodes[node_id].parent_node)).replace("'",'') == '<class __main__.MyTreeViewLabel>':
                node_id = self.uid2id[self.nodes[node_id].parent_node.uid]
            else:
                break
        node_names.reverse()
        return node_names


class MyBoxLayout(BoxLayout):
    background_color = ColorProperty() # The ListProperty will also work.


class LoadDialog(FloatLayout):
    loaddb = ObjectProperty(None)
    cancel = ObjectProperty(None)

class LoadYoutubeDialog(FloatLayout):
    loadyotube = ObjectProperty(None)
    cancel = ObjectProperty(None)
    def __init__(self, **kwargs):
        super(LoadYoutubeDialog, self).__init__(**kwargs)
        self.lecture_type = 'youtube'

    def checkbox_click(self, instance, value, lecture_type):
        self.lecture_type = lecture_type
        if lecture_type == 'youtube':
            self.ids.filechooser.disabled = True
            self.ids.video_id.disabled = False
            self.ids.video_name.disabled = False
        else:
            self.ids.filechooser.disabled = False
            self.ids.video_id.disabled = True
            self.ids.video_name.disabled = True

    def ok_click(self, youtube_id, lecture_name, path, selection):
        if self.lecture_type == 'youtube' and len(youtube_id) > 9 and lecture_name:
            cur.execute('SELECT id FROM audios WHERE id = ?;', (youtube_id,))
            request = cur.fetchall()
            if len(request) < 1:
                cur.execute('SELECT name FROM audios WHERE name = ?;', (lecture_name,))
                request = cur.fetchall()
                if len(request) < 1:
                    try:
                        subtitles = YouTubeTranscriptApi.get_transcript(self.ids.video_id.text, languages=['ru'])
                        self.loadyotube(self.lecture_type, youtube_id, lecture_name, subtitles, path, selection)
                    except TranscriptsDisabled:
                        self.ids.video_id.text = ''
                        return
                else:
                    self.ids.video_name.text = ''
            else:
                self.ids.video_id.text = ''
        else:
            return

class MyGrid(Widget):
    tag = ObjectProperty(None)
    mention = ObjectProperty(None)

    def __init__(self, **kwargs):
        super(MyGrid, self).__init__(**kwargs)
        self.tvedit_regim = 'Добавление'
        self.tvedit_current_id = 0
        self.tvedit_captured_id = -1
        self.ids.btn_tvedit_change.text = self.tvedit_regim
        self.ids.btn_tvedit_minus.disabled = True
        self.ids.btn_tvedit_minus.text = ''
        self.ids.btn_tvedit_plus.disabled = True
        self.ids.btn_tvedit_plus.text = '+'
        self.ids.tvedit_text.text = ''
        self.ids.tvedit_text.readonly = False
        cur.execute('SELECT id, name FROM audios;')
        self.yotube_id2name = {x[0]: x[1] for x in cur.fetchall()}
        self.name2yotube_id = {self.yotube_id2name[x]: x for x in self.yotube_id2name}
        self.ids.lecture.values = self.name2yotube_id.keys()
        self.current_youtube_id = ''
        self.timestamps = {}
        self.enterstamps = {}
        self.conspect_ids = {}
        self.conspect2icon = {}
        self.conspect_tags = {}


    def cancel_dialog(self):
        self._popup.dismiss()

    def show_load_youtube_dialog(self):
        content = LoadYoutubeDialog(loadyotube=self.loadyotube, cancel=self.cancel_dialog)
        self._popup = Popup(title="Выбрать mytetra.xml", content=content,
                            size_hint=(0.9, 0.9))
        self._popup.open()

    def loadyotube(self, lecture_type, youtube_id, lecture_name, subtitles, path, filename):
        """ Загрузка субтитров с youtube или pdf файла целиком"""
        transcr = ''
        timestamps = []
        cur.execute('INSERT INTO audios VALUES(?, ?, ?, ?, ?, ?, ?);',
                    (youtube_id, lecture_name, '',datetime.utcnow(), 0, '',my_user_id))
        cr = 0
        for subtitle in subtitles:
            timestamps.append((len(transcr), youtube_id, subtitle['start'], my_user_id))
            last_subtitle = subtitle['start']
            self.timestamps[len(transcr)] = subtitle['start']
            transcr += subtitle['text'] + ' '
        self.timestamps[len(transcr)] = last_subtitle
        timestamps.append((len(transcr), youtube_id, last_subtitle, my_user_id))
        cur.executemany('INSERT INTO timestamps VALUES(?, ?, ?, ?);', timestamps)
        cur.execute('UPDATE audios SET transcription=? WHERE id=?;', (transcr, youtube_id))
        conn.commit()
        cur.execute('SELECT id, name FROM audios;')
        self.yotube_id2name = {x[0]: x[1] for x in cur.fetchall()}
        self.name2yotube_id = {self.yotube_id2name[x]: x for x in self.yotube_id2name}
        self.ids.lecture.values = self.name2yotube_id.keys()
        self.cancel_dialog()

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
        if self.tvedit_regim == 'Добавление':
            cur.execute('SELECT max(id) FROM tags')
            request = cur.fetchone()
            cur.execute('INSERT INTO tags VALUES(?, ?, ?, ?);', (
                request[0] + 1, self.tvedit_current_id, self.ids.tvedit_text.text, my_user_id))
            conn.commit()
            my_tree_view_label = MyTreeViewLabel(
                text=self.ids.tvedit_text.text, is_open=True, external_id=request[0] + 1)
            my_tree_view_label.bind(on_touch_down=my_tree_view_label.label_touch)
            tree_node = self.tag.add_node(my_tree_view_label, self.tag.nodes[self.tvedit_current_id])
            self.tag.uid2id[tree_node.uid] = request[0] + 1
            self.tag.id2uid[request[0] + 1] = tree_node.uid
            self.tag.nodes[request[0] + 1] = tree_node
            self.ids.tvedit_text.text = ''
        elif self.tvedit_regim == 'Редактирование':
            cur.execute("UPDATE tags SET name=?, user_id=? WHERE id=?", (self.ids.tvedit_text.text, my_user_id,
                                                                         self.tvedit_current_id))
            conn.commit()
            self.tag.nodes[self.tvedit_current_id].text = self.ids.tvedit_text.text
        elif self.tvedit_regim == 'Удаление':
            cur.execute("DELETE FROM tags WHERE id=?", (self.tvedit_current_id,))
            conn.commit()
            self.tag.remove_node(self.tag.nodes[self.tvedit_current_id])
            self.tag.nodes.pop(self.tvedit_current_id)
            self.tag.uid2id.pop(self.tag.id2uid[self.tvedit_current_id])
            self.tag.id2uid.pop(self.tvedit_current_id)
            self.ids.tvedit_text.text = ''
        else:                     # Перенос
            cur.execute("UPDATE tags SET parent=?, user_id=? WHERE id=?", (self.tvedit_current_id, my_user_id,
                                                                         self.tvedit_captured_id))
            conn.commit()
            self.tag.reload_tree()
            self.ids.tvedit_text.text = ''
            self.ids.btn_tvedit_plus.disabled = True
            self.ids.btn_tvedit_minus.text = 'ok'
            self.tvedit_captured_id = -1

    def tv_touch(self, value):
        """ Нажатие на элемент дерева тэгов"""
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
        self.ids.tag_path.text = '\\'.join(self.tag.parent_list(self.tvedit_current_id))





        #self.ids.mention.data =

    def tvedit_text_click(self):
        if self.tvedit_regim == 'Добавление':
            if self.ids.tvedit_text.text:
                self.ids.btn_tvedit_plus.disabled = False
            else:
                self.ids.btn_tvedit_plus.disabled = True
        elif self.tvedit_regim == 'Редактирование':
            if self.ids.tvedit_text.text != self.tag.nodes[self.tvedit_current_id].text:
                self.ids.btn_tvedit_plus.disabled = False
            else:
                self.ids.btn_tvedit_plus.disabled = True

    def spn_lecture_click(self, value):
        """ Выбор лекции"""
        cur.execute('SELECT transcription FROM audios WHERE id = ?;', (self.name2yotube_id[value],))
        self.current_youtube_id = self.name2yotube_id[value]
        lecture = cur.fetchone()
        text = lecture[0]
        cur.execute('SELECT symbol_number FROM enterstamps WHERE audio_id = ? ORDER BY symbol_number;',
                    (self.name2yotube_id[value],))
        self.enterstamps = {x[0]: '\n' for x in cur.fetchall()}
        cur.execute('SELECT second, symbol_number FROM timestamps WHERE audio_id = ? ORDER BY symbol_number;',
                    (self.name2yotube_id[value],))
        self.timestamps = {x[1]: x[0] for x in cur.fetchall()}
        for i, enterstamp in enumerate(self.enterstamps):
            text = text[:enterstamp + i] + '\n' + text[enterstamp + i:]
        conspects = connd.execute(
            'SELECT * FROM conspects WHERE audio_id = ? ORDER BY symbol_number;', (self.name2yotube_id[value],))
        for conspect in conspects:
            if self.conspect_ids.get(conspect['symbol_number']):
                self.conspect_ids[conspect['symbol_number']][
                    conspect['user_id'] + '_' + str(conspect['tag_id'])] = conspect['content']
                self.conspect2icon[conspect['symbol_number']] = '*'
            else:
                self.conspect_ids[conspect['symbol_number']] = {
                    conspect['user_id'] + '_' + str(conspect['tag_id']): conspect['content']}
            if self.conspect_tags.get(conspect['tag_id']):
                self.conspect_tags[conspect['tag_id']][
                    conspect['user_id'] + '_' + str(conspect['symbol_number'])] = conspect['content']
            else:
                self.conspect_tags[conspect['tag_id']] = {
                    conspect['user_id'] + '_' + str(conspect['symbol_number']): conspect['content']}

        for i, conspect_symbol in enumerate(self.conspect_ids.keys()):
            text = text[:conspect_symbol + i + 1] + self.conspect2icon[conspect_symbol] + text[conspect_symbol + i + 1:]
        self.ids.transcript_text.text = text

    def btn_conspect_click(self, value):
        self.ids.file_id_time.text = '{:.2f}'.format(value)

    def transcript_text_click(self):
        text_index = self.ids.transcript_text.cursor_index()
        text_index_delta = len(list([x for x in self.enterstamps.keys() if x <= text_index])) + \
                           len(list([x for x in self.conspect_ids.keys() if x <= text_index]))
        text_index_original = text_index - text_index_delta
        if self.current_youtube_id:
            tir_left = max(list([x for x in self.timestamps.keys() if x <= text_index_original]))
            tir_right = min(list([x for x in self.timestamps.keys() if x > text_index_original]))
            self.ids.file_id_time.text = '{:.2f}'.format(
                self.timestamps[tir_left] + (text_index_original - tir_left)
                * (self.timestamps[tir_right] - self.timestamps[tir_left])/(tir_right - tir_left))

    def transcript_text_double_click(self):
        text_index = self.ids.transcript_text.cursor_index()
        text_index_delta = len(list([x for x in self.enterstamps.keys() if x <= text_index])) + \
                           len(list([x for x in self.conspect_ids.keys() if x <= text_index]))
        text_index_original = text_index - text_index_delta
        if self.current_youtube_id:
            if self.enterstamps.get(text_index_original):
                self.ids.transcript_text.text = self.ids.transcript_text.text[:text_index - 1] \
                                                + self.ids.transcript_text.text[text_index:]
                cur.execute('DELETE FROM enterstamps WHERE symbol_number=?;', (text_index_original,))
                conn.commit()
                self.enterstamps.pop(text_index_original)
            else:
                self.enterstamps[text_index_original] = '\n'
                self.ids.transcript_text.text = self.ids.transcript_text.text[:text_index] + '\n' \
                                                + self.ids.transcript_text.text[text_index:]
                cur.execute('INSERT INTO enterstamps VALUES(?,?);', (text_index_original, self.current_youtube_id))
                conn.commit()

    def btn_plus_conspect_click(self):
        """ Добавление конспекта
        Не проработан вариант редактирования, будет ошибка если уже есть
        комбинация symbol_number, audio_id, tag_id, user_id"""
        if self.ids.short_text.text and self.current_youtube_id and self.tvedit_current_id:
            text_index = self.ids.transcript_text.cursor_index()
            text_index_delta = len(list([x for x in self.enterstamps.keys() if x <= text_index])) + \
                               len(list([x for x in self.conspect_ids.keys() if x <= text_index]))
            text_index_original = text_index - text_index_delta
            tir_left = max(list([x for x in self.timestamps.keys() if x <= text_index_original]))
            tir_right = min(list([x for x in self.timestamps.keys() if x > text_index_original]))
            #                 symbol_number INT,
            #                 audio_id TEXT,
            #                 hash TEXT,
            #                 content TEXT NOT NULL,
            #                 edited DATETIME,
            #                 second REAL,
            #                 page INT,
            #                 tag_id INT,
            #                 pdf_id TEXT,
            #                 user_id TEXT,
            cur.execute('INSERT INTO conspects VALUES(?,?,?,?,?,?,?,?,?,?);', (
                text_index_original,
                self.current_youtube_id,
                hashlib.md5(self.ids.short_text.text.encode('utf-8')).hexdigest(),
                self.ids.short_text.text,
                datetime.utcnow(),
                self.timestamps[tir_left] + (text_index_original - tir_left) * (
                        self.timestamps[tir_right] - self.timestamps[tir_left]) / (tir_right - tir_left),
                None,
                self.tvedit_current_id,
                None,
                my_user_id))
            conn.commit()
            if self.conspect_ids.get(text_index_original):
                self.conspect_ids[text_index_original][
                    my_user_id + '_' + str(self.tvedit_current_id)] = self.ids.short_text.text
                self.conspect2icon[text_index_original] = '*'
            else:
                self.conspect_ids[text_index_original] = {
                    my_user_id + '_' + str(self.tvedit_current_id): self.ids.short_text.text}
                self.conspect2icon[text_index_original] = '+'
            if self.conspect_tags.get(self.tvedit_current_id):
                self.conspect_tags[self.tvedit_current_id][
                    my_user_id + '_' + str(text_index_original)] = self.ids.short_text.text
            else:
                self.conspect_tags[self.tvedit_current_id] = {
                    my_user_id + '_' + str(text_index_original): self.ids.short_text.text}
            text = self.ids.transcript_text.text
            self.ids.transcript_text.text = text[:text_index] + self.conspect2icon[text_index_original] \
                                            + text[text_index:]

    def transcript_text_changed(self, *args):
        """ Пока не используем. Посмотрим будут ли глюки со скролбаром """
        width_calc = self.grid.ids.scroller.width
        for line_label in self.grid.ids.ti._lines_labels:
            width_calc = max(width_calc, line_label.width + 20)   # add 20 to avoid automatically creating a new line
        self.ids.transcript_text.width = width_calc


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
            CREATE TABLE IF NOT EXISTS enterstamps(
                symbol_number INT,                
                audio_id TEXT,
                CONSTRAINT id PRIMARY KEY (symbol_number, audio_id),
                FOREIGN KEY (audio_id) REFERENCES audios(id));""")
        conn.commit()
        cur.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_symbol_number ON enterstamps (symbol_number);""")
        conn.commit()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS timestamps(
                symbol_number INT,                
                audio_id TEXT,
                second REAL,
                user_id TEXT,
                CONSTRAINT id PRIMARY KEY (symbol_number, audio_id),
                FOREIGN KEY (audio_id) REFERENCES audios(id),
                FOREIGN KEY (user_id) REFERENCES users(id));""")
        conn.commit()
        cur.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_symbol_number ON timestamps (symbol_number);""")
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
                symbol_number INT,                    
                audio_id TEXT,
                hash TEXT,
                content TEXT NOT NULL,                    
                edited DATETIME,
                second REAL,
                page INT,
                tag_id INT,
                pdf_id TEXT,
                user_id TEXT,
                CONSTRAINT id PRIMARY KEY (symbol_number, audio_id, tag_id, user_id),
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
            connd = sqlite3.connect(os.path.join(APP_PATH, 'main.db'))
            connd.row_factory = sqlite3.Row

    Factory.register('LoadDialog', cls=LoadDialog)
    my_user_id = 'q1q1'
    my_user_name = 'Денис Алексеев'
    TrainerApp().run()

