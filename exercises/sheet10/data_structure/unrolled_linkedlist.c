#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "unrolled_linkedlist.h"

static UnrolledNode *create_node(size_t capacity)
{
    UnrolledNode *node = malloc(sizeof(UnrolledNode));
    if (!node)
        return NULL;

    node->elements = calloc(capacity, sizeof(int));
    if (!node->elements)
    {
        free(node);
        return NULL;
    }

    node->count = 0;
    node->capacity = capacity;
    node->next = NULL;
    node->prev = NULL;

    return node;
}

static void free_node(UnrolledNode *node)
{
    if (node)
    {
        free(node->elements);
        free(node);
    }
}

void unrolled_linkedlist_print(UnrolledLinkedList *list)
{
    UnrolledNode *current = list->head;
    size_t index = 0;

    while (current)
    {
        printf("Node %zu: ", index++);
        for (size_t i = 0; i < current->count; i++)
        {
            printf("%d ", current->elements[i]);
        }
        printf("\n");
        current = current->next;
    }
}

static UnrolledNode *find_node_by_index(UnrolledLinkedList *list, size_t index, size_t *local_index)
{
    if (index >= list->total_elements)
        return NULL;

    UnrolledNode *current = list->head;
    size_t cumulative = 0;

    while (current)
    {
        if (cumulative + current->count > index)
        {
            *local_index = index - cumulative;
            return current;
        }
        cumulative += current->count;
        current = current->next;
    }

    return NULL;
}

static void split_node_if_full(UnrolledLinkedList *list, UnrolledNode *node)
{
    if (node->count < node->capacity)
        return;

    UnrolledNode *new_node = create_node(node->capacity);
    if (!new_node)
        return;

    size_t mid = node->count / 2;
    size_t move_count = node->count - mid;

    memcpy(new_node->elements, &node->elements[mid], move_count * sizeof(int));
    new_node->count = move_count;
    node->count = mid;

    new_node->next = node->next;
    new_node->prev = node;

    if (node->next)
    {
        node->next->prev = new_node;
    }
    else
    {
        list->tail = new_node;
    }

    node->next = new_node;
}

static void merge_nodes_if_sparse(UnrolledLinkedList *list, UnrolledNode *node)
{
    if (!node || !node->next)
        return;

    size_t threshold = node->capacity / 4;
    if (node->count > threshold || node->next->count > threshold)
        return;

    if (node->count + node->next->count > node->capacity)
        return;

    UnrolledNode *next_node = node->next;

    memcpy(&node->elements[node->count], next_node->elements,
           next_node->count * sizeof(int));
    node->count += next_node->count;

    node->next = next_node->next;
    if (next_node->next)
    {
        next_node->next->prev = node;
    }
    else
    {
        list->tail = node;
    }

    free_node(next_node);
}

static void unrolled_init(void *data, size_t size, size_t element_size)
{
    UnrolledLinkedList *list = (UnrolledLinkedList *)data;

    list->head = NULL;
    list->tail = NULL;
    list->total_elements = 0;

    if (size > 0)
    {
        size_t nodes_needed = (size + list->chunk_capacity - 1) / list->chunk_capacity;

        for (size_t i = 0; i < nodes_needed; i++)
        {
            UnrolledNode *node = create_node(list->chunk_capacity);
            if (!node)
                break;

            size_t remaining = size - list->total_elements;
            size_t elements_in_node = (remaining > list->chunk_capacity) ? list->chunk_capacity : remaining;

            memset(node->elements, 0, elements_in_node * sizeof(int));
            node->count = elements_in_node;
            list->total_elements += elements_in_node;

            if (!list->head)
            {
                list->head = list->tail = node;
            }
            else
            {
                list->tail->next = node;
                node->prev = list->tail;
                list->tail = node;
            }
        }
    }
}

static int unrolled_read(void *data, size_t index)
{
    UnrolledLinkedList *list = (UnrolledLinkedList *)data;
    size_t local_index;

    UnrolledNode *node = find_node_by_index(list, index, &local_index);
    if (!node)
        return -1;

    return node->elements[local_index];
}

static void unrolled_write(void *data, size_t index, int value)
{
    UnrolledLinkedList *list = (UnrolledLinkedList *)data;
    size_t local_index;

    UnrolledNode *node = find_node_by_index(list, index, &local_index);
    if (!node)
        return;

    node->elements[local_index] = value;
}

static int unrolled_insert(void *data, size_t index, int value)
{
    UnrolledLinkedList *list = (UnrolledLinkedList *)data;
    if (!list->head)
    {
        UnrolledNode *node = create_node(list->chunk_capacity);
        if (!node)
            return -1;

        node->elements[0] = value;
        node->count = 1;
        list->head = list->tail = node;
        list->total_elements = 1;
        return 0;
    }

    if (index >= list->total_elements)
    {
        UnrolledNode *last = list->tail;

        if (last->count < last->capacity)
        {
            last->elements[last->count++] = value;
        }
        else
        {
            UnrolledNode *new_node = create_node(list->chunk_capacity);
            if (!new_node)
                return -1;

            new_node->elements[0] = value;
            new_node->count = 1;
            new_node->prev = last;
            last->next = new_node;
            list->tail = new_node;
        }

        list->total_elements++;
        return 0;
    }

    size_t local_index;
    UnrolledNode *node = find_node_by_index(list, index, &local_index);
    if (!node)
        return -1;

    if (node->count < node->capacity)
    {
        memmove(&node->elements[local_index + 1],
                &node->elements[local_index],
                (node->count - local_index) * sizeof(int));
        node->elements[local_index] = value;
        node->count++;
        list->total_elements++;
        return 0;
    }

    split_node_if_full(list, node);

    if (local_index >= node->count)
    {
        local_index -= node->count;
        node = node->next;
    }

    memmove(&node->elements[local_index + 1],
            &node->elements[local_index],
            (node->count - local_index) * sizeof(int));
    node->elements[local_index] = value;
    node->count++;
    list->total_elements++;

    return 0;
}

static int unrolled_delete(void *data, size_t index)
{
    UnrolledLinkedList *list = (UnrolledLinkedList *)data;

    if (index >= list->total_elements)
        return -1;

    size_t local_index;
    UnrolledNode *node = find_node_by_index(list, index, &local_index);
    if (!node)
        return -1;

    memmove(&node->elements[local_index],
            &node->elements[local_index + 1],
            (node->count - local_index - 1) * sizeof(int));

    node->count--;
    list->total_elements--;

    if (node->count == 0)
    {
        if (node->prev)
        {
            node->prev->next = node->next;
        }
        else
        {
            list->head = node->next;
        }

        if (node->next)
        {
            node->next->prev = node->prev;
        }
        else
        {
            list->tail = node->prev;
        }

        free_node(node);
    }
    else
    {
        merge_nodes_if_sparse(list, node);
    }

    return 0;
}

static void unrolled_cleanup(void *data)
{
    UnrolledLinkedList *list = (UnrolledLinkedList *)data;

    UnrolledNode *current = list->head;
    while (current)
    {
        UnrolledNode *next = current->next;
        free_node(current);
        current = next;
    }

    list->head = list->tail = NULL;
    list->total_elements = 0;
}

Container create_unrolled_linkedlist(size_t chunk_capacity)
{
    Container container = {0};

    UnrolledLinkedList *list = malloc(sizeof(UnrolledLinkedList));
    if (!list)
    {
        return container;
    }

    list->head = NULL;
    list->tail = NULL;
    list->total_elements = 0;
    list->chunk_capacity = chunk_capacity;

    container.data = list;
    container.element_size = sizeof(int);
    container.read = unrolled_read;
    container.write = unrolled_write;
    container.insert = unrolled_insert;
    container.delete = unrolled_delete;
    container.init = unrolled_init;
    container.cleanup = unrolled_cleanup;

    return container;
}

Container create_unrolled_linkedlist_8()
{
    return create_unrolled_linkedlist(8);
}

Container create_unrolled_linkedlist_16()
{
    return create_unrolled_linkedlist(16);
}

Container create_unrolled_linkedlist_32()
{
    return create_unrolled_linkedlist(32);
}

Container create_unrolled_linkedlist_64()
{
    return create_unrolled_linkedlist(64);
}

Container create_unrolled_linkedlist_128()
{
    return create_unrolled_linkedlist(128);
}

Container create_unrolled_linkedlist_256()
{
    return create_unrolled_linkedlist(256);
}