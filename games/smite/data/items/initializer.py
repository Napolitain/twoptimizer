import os

# loop through all files in the current dir, and if it is python file which is not "initializer" or "__init__" file, rename to append item_ to the start of the file name

for file in os.listdir():
    if file.endswith('.py') and file != 'initializer.py' and file != '__init__.py':
        os.rename(file, f'item_{file}')
