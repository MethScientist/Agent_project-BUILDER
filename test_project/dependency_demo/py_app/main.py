from py_app.utils.math_utils import add, Greeter

def main():
    result = add(2, 3)
    greeting = Greeter("Hope").greet()
    print(greeting)
    print(result)

if __name__ == "__main__":
    main()