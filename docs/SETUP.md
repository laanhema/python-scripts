### Complete Portable Setup - Wrapper Script + Symlink

1. **Fix permissions:**

```bash
chmod +x /path/to/file/python-scripts/wrapper-scripts/brk
```

2. **Create symlink:**

```bash
sudo ln -sf /path/to/file/python-scripts/wrapper-scripts/brk ~/.local/bin/brk
```

3. **Add to PATH (if not already there):**

```bash
export PATH="$HOME/.local/bin:$PATH"

# Add to appropriate shell config file
cat >> ~/.bashrc << 'EOF'
export PATH="$HOME/.local/bin:$PATH"
EOF
source ~/.bashrc
```

4. **Usage:**

```bash
brk
```
