with open('data/qlib_data/instruments/all.txt', 'r') as f:
    lines = f.readlines()[:100]

with open('data/qlib_data/instruments/test_subset.txt', 'w') as f:
    f.writelines(lines)
