from py_app.utils.math_utils import add, Greeter

def main():
    total = add(2, 3)
    greeting = Greeter("Hope").greet()
    print(total)
    print(greeting)

if __name__ == "__main__":
    main()