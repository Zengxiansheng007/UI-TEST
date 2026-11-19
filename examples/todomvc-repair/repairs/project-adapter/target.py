class Target:
    def __init__(self, todo, text):
        # The project adapter scopes the foreign rows without editing their provider.
        self.row = todo.rows.filter(has=todo.page.get_by_text(text, exact=True))
