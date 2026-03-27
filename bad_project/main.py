# main.py
from math_ops import add, subtract
from utils import helper

def main():
    x = add(5, 3)
    y = subtract(10, 4)
    z = helper(x, y)  # helper intentionally missing in utils.py
    print(z)

main()
