Each .py file represents it's own program that can be run either from the command line like
'python server.py'
'python client.py'
or
'python3 server.py'
'python3 client.py'
depending on your installation (for me, the first one worked) or by copy pasting the code in
the files into respective code cells in two seperate Jupyter Notebooks. The latter method is
how I did the most tests for my code. If you want to test multiple clients in this way, however,
you will need to copy the client code into yet a third jupyter notebook.

From there, my text-based interface should be pretty intuitive.

When a user sends a message, it's marked as read by them by default, so if you need to test the
'read new messages' functionality you will have to either exit the client program and start another
with a different username or run a seperate client instance concurrently.