# AI usage

## Tools

I used DeepSeek for the tests. We read SPEC.md a bit at a time and wrote unit, API, contract
and CORS tests. Then a small script that breaks one behaviour at a time and runs the suite.

## What AI got wrong

My first inbox test had one card per branch so it passed even if the sort did nothing. I moved
all four transfers to one branch and sent them normal, urgent, high, urgent, which catches it.
The CORS test also only checked the allowed origin so I added a made-up origin and check it
gets 400 with no access-control-allow-origin.

## In my own words

1. Pick one mutant your first draft of tests did not kill. Why not, and what did you add?

M10 the inbox sort. At first I had one card per branch so the order looked fine, then I sent
normal urgent high urgent to the same branch and the normal card came first so the test failed.

2. Why is a test that only asserts status_code == 409 weaker than one that asserts the problem type?

A 409 can come from three different checks here so if the test only checks the code any of them
passes. The type says which rule actually fired.
