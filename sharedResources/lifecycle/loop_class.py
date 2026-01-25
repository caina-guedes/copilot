import asyncio

class MyLoop():
        """ 
            em breve mudarei o loop pra ser uma classe com o 
            atributo currrent, por enquanto é uma lista com o primeiro elemento 
            sendo o loop de fato
        """
        _current = None

        @classmethod
        def instance_check(cls, loop = None):
            if loop is None:
                return isinstance(cls.get(), asyncio.AbstractEventLoop)
            else:
                return isinstance(loop, asyncio.AbstractEventLoop)

        @classmethod
        def is_running(cls):
            if cls._current is None:
                print("o current loop ainda é None enquanto tentaram ver se ele estava rodando")
                return False
            if cls.instance_check():
                return cls._current.is_running()
            else:
                print("tentaram ver se o loop estava rodando mas ele nem é um loop")

        @classmethod
        def is_closed(cls):
            if cls._current is None:
                print("o current loop ainda é None enquanto tentaram ver se ele estava fechado")
                return True
            if cls.instance_check():
                return cls._current.is_closed()
            else:
                print("tentaram ver se o loop está fechado mas ele não é um loop!")
        

  
        @classmethod
        def set(cls,loop):
            if cls._current is None:
                if cls.instance_check(loop):
                    cls._current = loop
                else:
                    print("the argument is not a proper loop to set in the main loop")
            else:
                print("current loop already set!")
        
        @classmethod
        def get(cls):
            return cls._current


        @classmethod
        def _loop_is_ok(cls,register = None):
            def reg_helper(msg):
                if register is not None:
                    register(msg,"general")
                else:
                    print(msg)

            if cls.get() is None :
                cls.reg_helper("[loop_is_ok] cls.running_loop is empty!")
                return False
            
            if cls.instance_check():
                if not cls.is_running():
                    cls.reg_helper("[loop_is_ok] loop is not running")

                if cls.is_closed():
                    cls.reg_helper("[loop_is_ok] loop is closed")
                    return False
                else:
                    return True
            else:
                cls.reg_helper(f"[loop_is_ok] loop is not what it is supposed to be and it is: {type(cls.get())}")
                return False
