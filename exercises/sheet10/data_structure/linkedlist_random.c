#include "linkedlist_basic.h"

static void linkedlist_init(void *data, size_t size, size_t element_size)
{
    LinkedListData *list = (LinkedListData *)data;
    list->head = NULL;
    list->size = 0;
    list->element_size = element_size;
    list->current = NULL;
    list->current_index = 0;

    if (size == 0)
        return;

    size_t *allocation_order = (size_t *)malloc(size * sizeof(size_t));
    if (!allocation_order)
    {
        fprintf(stderr, "Error: Failed to allocate memory for allocation order\n");
        exit(1);
    }

    for (size_t i = 0; i < size; i++)
    {
        allocation_order[i] = i;
    }

    // Fisher-Yates shuffle
    for (size_t i = size - 1; i > 0; i--)
    {
        size_t j = rand() % (i + 1);
        size_t temp = allocation_order[i];
        allocation_order[i] = allocation_order[j];
        allocation_order[j] = temp;
    }

    Node **nodes = (Node **)calloc(size, sizeof(Node *));
    if (!nodes)
    {
        free(allocation_order);
        fprintf(stderr, "Error: Failed to allocate memory for node pointers\n");
        exit(1);
    }

    for (size_t alloc_step = 0; alloc_step < size; alloc_step++)
    {
        size_t logical_index = allocation_order[alloc_step];

        void *frag_ptr = malloc(16 + (rand() % 32)); // 16-48 bytes
        free(frag_ptr);

        nodes[logical_index] = (Node *)malloc(sizeof(Node));
        if (!nodes[logical_index])
        {
            for (size_t cleanup = 0; cleanup < size; cleanup++)
            {
                if (nodes[cleanup])
                    free(nodes[cleanup]);
            }
            free(allocation_order);
            free(nodes);
            fprintf(stderr, "Error: Failed to allocate memory for node at index %zu\n", logical_index);
            exit(1);
        }

        nodes[logical_index]->value = logical_index % 1000;
        nodes[logical_index]->next = NULL;
    }

    for (size_t i = 0; i < size - 1; i++)
    {
        nodes[i]->next = nodes[i + 1];
    }

    list->head = nodes[0];
    list->size = size;
    list->current = list->head;
    list->current_index = 0;

    free(allocation_order);
    free(nodes);
}

Container create_linkedlist_random()
{
    Container container;
    LinkedListData *list_data = (LinkedListData *)malloc(sizeof(LinkedListData));
    if (!list_data)
    {
        fprintf(stderr, "Error: Failed to allocate memory for linked list container\n");
        exit(1);
    }

    list_data->head = NULL;
    list_data->size = 0;
    list_data->element_size = sizeof(int);
    list_data->current = NULL;
    list_data->current_index = 0;

    container.data = list_data;
    container.element_size = list_data->element_size;
    container.read = linkedlist_read;
    container.write = linkedlist_write;
    container.insert = linkedlist_insert;
    container.delete = linkedlist_delete;
    container.init = linkedlist_init;
    container.cleanup = linkedlist_cleanup;

    return container;
}