#!/usr/bin/env python3
import os
import re
import sys
import argparse

def find_block(text, block_name):
    """Return (start, end) indices of the named block, tracking brace depth."""
    pattern = re.compile(rf'(?m)^\s*{re.escape(block_name)}\s*\{{')
    m = pattern.search(text)
    if not m:
        return None
    start = m.start()
    depth = 0
    i = start
    while i < len(text):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return (start, i + 1)
        i += 1
    raise ValueError(f"Unmatched brace for block '{block_name}'")

def indent(text, spaces):
    pad = ' ' * spaces
    return '\n'.join(pad + line if line.strip() else line
                     for line in text.splitlines())

def build_block(name, shader_text, config_text=None):
    lines = [f'    {name} {{']
    if config_text:
        for line in config_text.splitlines():
            if line.strip():
                lines.append(f'        {line.strip()}')
    lines.append('        custom-shader r"')
    lines.append(indent(shader_text.strip(), 12))
    lines.append('        "')
    lines.append('    }')
    return '\n'.join(lines)

def install_block(anim_content, block_name, replacement):
    """Replace or insert a named block within anim_content."""
    loc = find_block(anim_content, block_name)
    if loc:
        return anim_content[:loc[0]] + replacement + anim_content[loc[1]:]
    else:
        return anim_content[:-1] + '\n' + replacement + '\n}'

def delete_block(anim_content, block_name):
    """Remove a named block from anim_content, including its leading newline."""
    loc = find_block(anim_content, block_name)
    if not loc:
        return anim_content
    start, end = loc
    while start > 0 and anim_content[start - 1] in (' ', '\t'):
        start -= 1
    if start > 0 and anim_content[start - 1] == '\n':
        start -= 1
    return anim_content[:start] + anim_content[end:]

def ensure_animations_block(text, operations):
    """
    operations: list of (block_name, action, replacement)
      action is 'install', 'delete', or 'skip'
    """
    anim = find_block(text, 'animations')

    if not anim:
        new_blocks = '\n\n'.join(
            repl for _, action, repl in operations
            if action == 'install' and repl is not None
        )
        if not new_blocks:
            return text
        return text + f'\nanimations {{\n{new_blocks}\n}}\n'

    anim_start, anim_end = anim
    anim_content = text[anim_start:anim_end]

    for block_name, action, replacement in operations:
        if action == 'delete':
            anim_content = delete_block(anim_content, block_name)
        elif action == 'install':
            anim_content = install_block(anim_content, block_name, replacement)
        # 'skip' — leave untouched

    return text[:anim_start] + anim_content + text[anim_end:]

def main():
    parser = argparse.ArgumentParser(
        description='Install or delete niri window animation shaders.'
    )
    parser.add_argument('shader_dir', nargs='?',
                        help='Directory containing open.glsl, close.glsl, resize.glsl, and optional config files')
    parser.add_argument('-o', '--open',      action='store_true', help='Target the open animation')
    parser.add_argument('-c', '--close',     action='store_true', help='Target the close animation')
    parser.add_argument('-r', '--resize',    action='store_true', help='Target the resize animation')
    parser.add_argument('-d', '--delete',    action='store_true', help='Delete the animation block(s) instead of installing')
    parser.add_argument('-n', '--no-config', action='store_true', help='Ignore config file and install shaders with no extra parameters')
    parser.add_argument('-C', '--niri-config',
                        default=os.path.join(os.path.expanduser('~'), '.config', 'niri', 'config.kdl'),
                        help='Path to the niri config file (default: ~/.config/niri/config.kdl)')
    args = parser.parse_args()

    # If no animation flags given, all are targeted by default
    any_explicit = args.open or args.close or args.resize
    target_open   = args.open   or not any_explicit
    target_close  = args.close  or not any_explicit
    target_resize = args.resize or not any_explicit

    if not args.delete and args.shader_dir is None:
        parser.error('shader_dir is required when not using --delete')

    if not args.delete and not os.path.isdir(args.shader_dir):
        print(f'Error: directory not found: {args.shader_dir}', file=sys.stderr)
        sys.exit(1)

    # Each animation: (block_name, file, targeted)
    animations = [
        ('window-open',   'open.glsl',   target_open),
        ('window-close',  'close.glsl',  target_close),
        ('window-resize', 'resize.glsl', target_resize),
    ]

    if args.delete:
        operations = [
            (block, 'delete' if targeted else 'skip', None)
            for block, _, targeted in animations
        ]
    else:
        config_text = None
        if not args.no_config:
            config_path = os.path.join(args.shader_dir, 'config')
            if os.path.isfile(config_path):
                with open(config_path, 'r') as f:
                    config_text = f.read()

        operations = []
        for block_name, filename, targeted in animations:
            if not targeted:
                operations.append((block_name, 'skip', None))
                continue

            filepath = os.path.join(args.shader_dir, filename)
            if not os.path.isfile(filepath):
                if any_explicit:
                    # Explicitly targeted but missing — delete the block
                    print(f'Warning: {filename} not found, deleting {block_name}', file=sys.stderr)
                    operations.append((block_name, 'delete', None))
                else:
                    # Default targeting — silently skip
                    operations.append((block_name, 'skip', None))
                continue

            with open(filepath, 'r') as f:
                shader = f.read()
            block = build_block(block_name, shader, config_text)
            operations.append((block_name, 'install', block))

    niri_config = args.niri_config
    with open(niri_config, 'r') as f:
        original = f.read()

    result = ensure_animations_block(original, operations)

    with open(niri_config, 'w') as f:
        f.write(result)

    for block_name, action, _ in operations:
        if action == 'install':
            print(f'Installed {block_name}')
        elif action == 'delete':
            print(f'Deleted {block_name}')

if __name__ == '__main__':
    main()
