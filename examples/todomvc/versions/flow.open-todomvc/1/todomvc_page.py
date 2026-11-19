"""TodoMVC公开练习的共享页面操作与即时断言。"""
from playwright.sync_api import expect

class TodoPage:
    def __init__(self, page):
        self.page = page  # 当前用例独立页面。
        self.input = page.get_by_placeholder('What needs to be done?')
        self.rows = page.locator('.todo-list li')
        self.counter = page.locator('.todo-count')

    def open(self, url, on_entry=None):
        if on_entry is not None:
            on_entry(self.page)
        self.page.goto(url, wait_until='domcontentloaded')  # 每例完整重放公开入口。
        expect(self.input).to_be_visible()
        expect(self.rows).to_have_count(0)

    def fill(self, text):
        self.input.fill(text)  # 输入后立即读取实际值。
        expect(self.input).to_have_value(text)

    def add(self, text, empty, counter):
        self.input.press('Enter')  # 唯一新增提交动作。
        expect(self.rows).to_have_count(1)
        expect(self.rows.locator('label')).to_have_text(text)
        expect(self.input).to_have_value(empty)
        expect(self.counter).to_have_text(counter)

    def ready_complete(self):
        expect(self.rows).to_have_count(1)  # 当前运行自行建立准备数据。
        expect(self.rows.get_by_role('checkbox')).not_to_be_checked()

    def complete(self, counter):
        self.rows.get_by_role('checkbox').check()  # 唯一完成更新动作。
        expect(self.rows.get_by_role('checkbox')).to_be_checked()
        expect(self.counter).to_have_text(counter)
        expect(self.page.get_by_role('button', name='Clear completed')).to_be_visible()
