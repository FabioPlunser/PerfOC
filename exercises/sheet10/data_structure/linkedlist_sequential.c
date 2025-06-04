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

    Node *prev = NULL;

    for (size_t i = 0; i < size; i++)
    {
        Node *new_node = (Node *)malloc(sizeof(Node));
        if (!new_node)
        {
            fprintf(stderr, "Error: Failed to allocate memory for linked list node\n");
            exit(1);
        }

        new_node->value = i % 1000;
        new_node->next = NULL;

        if (!list->head)
        {
            list->head = new_node;
        }
        else if (prev)
        {
            prev->next = new_node;
        }

        prev = new_node;
        list->size++;
    }

    list->current = list->head;
    list->current_index = 0;
}

Container create_linkedlist_sequential()
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