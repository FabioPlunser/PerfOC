CC = gcc
CFLAGS = -Wall -O2 -I. -Idata_structure -Ilib
LDFLAGS = 

# Source files
SRCS = benchmark.c lib/args_parser.c lib/container_registry.c
DS_SRCS = data_structure/array_container.c data_structure/linkedlist_sequential.c data_structure/linkedlist_random.c data_structure/unrolled_linkedlist.c data_structure/tiered_array.c
OBJS = $(SRCS:.c=.o) $(DS_SRCS:.c=.o)

# Test source files
TEST_SRCS = test/generate_sequence_test.c
TEST_OBJS = $(TEST_SRCS:.c=.o)
TEST_DEPS = lib/args_parser.o lib/container_registry.o data_structure/array_container.o \
            data_structure/linkedlist_sequential.o data_structure/linkedlist_random.o \
            data_structure/unrolled_linkedlist.o data_structure/tiered_array.o

# Target executable
TARGET = benchmark
TEST_TARGET = sequence_test
# Default target
all: $(TARGET) $(TEST_TARGET)

# Build the benchmark target
$(TARGET): $(OBJS)
	$(CC) $(LDFLAGS) $(OBJS) -o $(TARGET)

# Build the sequence test target
$(TEST_TARGET): $(TEST_OBJS) $(TEST_DEPS)
	$(CC) $(LDFLAGS) -o $@ $^

# Compile source files
%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

# Clean up
clean:
	rm -f $(OBJS) $(TARGET) $(TEST_OBJS) $(TEST_TARGET)

# Test targets
test-array:
	./$(TARGET) array 1000 8 1.0 3

test-linkedlist-seq:
	./$(TARGET) linkedlist_seq 1000 8 0.2 3

test-linkedlist-rand:
	./$(TARGET) linkedlist_rand 1000 8 0.2 3

test-unrolledlist:
	./$(TARGET) unrolled_linkedlist_8 1000 8 0.6 3
	./$(TARGET) unrolled_linkedlist_16 1000 8 0.6 3
	./$(TARGET) unrolled_linkedlist_32 1000 8 0.6 3
	./$(TARGET) unrolled_linkedlist_64 1000 8 0.6 3
	./$(TARGET) unrolled_linkedlist_128 1000 8 0.6 3
	./$(TARGET) unrolled_linkedlist_256 1000 8 0.6 3

test-tiers:
	./$(TARGET) tiered_array_8 1000 8 0.6 3
	./$(TARGET) tiered_array_16 1000 16 0.6 3
	./$(TARGET) tiered_array_32 1000 16 0.6 3
	./$(TARGET) tiered_array_64 1000 16 0.6 3
	./$(TARGET) tiered_array_128 1000 16 0.6 3
	./$(TARGET) tiered_array_256 1000 16 0.6 3

test-all:
	./$(TARGET) array 1000 8 1.0 1
	./$(TARGET) linkedlist_seq 1000 8 0.2 1
	./$(TARGET) linkedlist_rand 1000 8 0.2 1
	./$(TARGET) unrolled_linkedlist_8 1000 8 0.6 1
	./$(TARGET) tiered_array_8 1000 8 0.6 1

test-sequence:
	./$(TEST_TARGET)

.PHONY: all clean test-array test-linkedlist-seq test-linkedlist-rand test-unrolledlist test-sequence test-all