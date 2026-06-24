# Task: Prime numbers up to 50

Write a self-contained Python program that does the following:

1. Define a function `is_prime(n)` that returns `True` if `n` is a prime number
   and `False` otherwise. Numbers below 2 are not prime.
2. Find every prime number between 1 and 50 (inclusive).
3. Print the primes on a single line, separated by single spaces.
4. On the next line, print how many primes were found.

## Constraints

- Use only the Python standard library.
- The program must print its results to stdout (return values are not observed).

## Expected output

```
2 3 5 7 11 13 17 19 23 29 31 37 41 43 47
15
```

The program is only correct if its stdout matches the expected output exactly,
including the order of the numbers and the count on the second line.