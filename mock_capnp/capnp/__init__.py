
class Mock:
    def __getattr__(self, name):
        if name == 'enumerants': return {}
        return Mock()
    def __call__(self, *args, **kwargs): return Mock()
    def __iter__(self): return iter([])
lib = Mock()
lib.capnp = Mock()
lib.capnp._StructModule = Mock()
def load(*args, **kwargs): return Mock()
def remove_import_hook(): pass
