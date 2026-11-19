class Target:
    def __init__(self, todo, text):
        self.row = todo.rows.filter(has=todo.page.get_by_text(text, exact=True))  # Preserve the source row identity.
