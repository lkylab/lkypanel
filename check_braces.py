
def check_braces(filename):
    with open(filename, 'r') as f:
        content = f.read()
    
    stack = []
    line = 1
    col = 1
    for i, char in enumerate(content):
        if char == '\n':
            line += 1
            col = 1
        else:
            col += 1
            
        if char == '{':
            stack.append(('{', line, col))
        elif char == '}':
            if not stack:
                print(f"Extra closing brace at line {line}, col {col}")
                return
            stack.pop()
        elif char == '[':
            stack.append(('[', line, col))
        elif char == ']':
            if not stack:
                print(f"Extra closing bracket at line {line}, col {col}")
                return
            stack.pop()
        elif char == '(':
            stack.append(('(', line, col))
        elif char == ')':
            if not stack:
                print(f"Extra closing parenthesis at line {line}, col {col}")
                return
            stack.pop()
            
    if stack:
        for char, l, c in stack:
            print(f"Unclosed {char} starting at line {l}, col {c}")
    else:
        print("All braces/parentheses match.")

check_braces('lkypanel/filemanager/static/filemanager/fm_core.js')
