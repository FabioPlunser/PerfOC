#include "benchmark.h"
#include <stdlib.h>
#include <stdio.h>
#include <time.h>

typedef struct Node
{
  int value;
  struct Node *next;
} Node;

typedef struct
{
  Node *head;
  size_t size;
  bool random_allocation; // Allocation policy flag
  Node **preallocated;    // For random allocation policy
  size_t prealloc_size;
  size_t prealloc_used;
} LinkedList;

// Sequential allocation policy - allocate nodes in order
Node *alloc_sequential()
{
  return malloc(sizeof(Node));
}

// Random allocation policy - preallocate and shuffle for random memory layout
void setup_random_allocation(LinkedList *list, size_t max_nodes)
{
  list->preallocated = malloc(max_nodes * sizeof(Node *));
  list->prealloc_size = max_nodes;
  list->prealloc_used = 0;

  // Preallocate all nodes
  for (size_t i = 0; i < max_nodes; i++)
  {
    list->preallocated[i] = malloc(sizeof(Node));
  }

  // Shuffle the array to create random allocation order
  for (size_t i = max_nodes - 1; i > 0; i--)
  {
    size_t j = rand() % (i + 1);
    Node *temp = list->preallocated[i];
    list->preallocated[i] = list->preallocated[j];
    list->preallocated[j] = temp;
  }
}

Node *alloc_random(LinkedList *list)
{
  if (list->prealloc_used < list->prealloc_size)
  {
    return list->preallocated[list->prealloc_used++];
  }
  return malloc(sizeof(Node)); // Fallback if we run out
}

// Get element at index (O(n) operation)
int list_get(void *ds, size_t index)
{
  LinkedList *list = (LinkedList *)ds;
  Node *current = list->head;

  // Traverse to the index
  for (size_t i = 0; i < index && current; i++)
  {
    current = current->next;
  }

  return current ? current->value : 0;
}

// Set element at index (O(n) operation)
void list_set(void *ds, size_t index, int value)
{
  LinkedList *list = (LinkedList *)ds;
  Node *current = list->head;

  // Traverse to the index
  for (size_t i = 0; i < index && current; i++)
  {
    current = current->next;
  }

  if (current)
  {
    current->value = value;
  }
}

// Insert element at index (O(n) operation)
void list_insert(void *ds, size_t index, int value)
{
  LinkedList *list = (LinkedList *)ds;

  // Allocate new node based on allocation policy
  Node *new_node = list->random_allocation ? alloc_random(list) : alloc_sequential();
  new_node->value = value;

  // Insert at head (index 0)
  if (index == 0)
  {
    new_node->next = list->head;
    list->head = new_node;
  }
  else
  {
    // Find the node before insertion point
    Node *current = list->head;
    for (size_t i = 0; i < index - 1 && current; i++)
    {
      current = current->next;
    }

    if (current)
    {
      new_node->next = current->next;
      current->next = new_node;
    }
    else
    {
      // Index out of bounds, insert at end
      free(new_node);
      return;
    }
  }

  list->size++;
}

// Delete element at index (O(n) operation)
void list_delete(void *ds, size_t index)
{
  LinkedList *list = (LinkedList *)ds;

  // Don't delete if only one element left (as per exercise requirements)
  if (list->size <= 1)
    return;

  Node *to_delete = NULL;

  // Delete head (index 0)
  if (index == 0)
  {
    to_delete = list->head;
    list->head = list->head->next;
  }
  else
  {
    // Find the node before deletion point
    Node *current = list->head;
    for (size_t i = 0; i < index - 1 && current; i++)
    {
      current = current->next;
    }

    if (current && current->next)
    {
      to_delete = current->next;
      current->next = to_delete->next;
    }
  }

  // Free immediately as required by exercise
  if (to_delete)
  {
    free(to_delete);
    list->size--;
  }
}

// Destroy the entire linked list
void list_destroy(void *ds)
{
  LinkedList *list = (LinkedList *)ds;

  // Free all nodes in the list
  Node *current = list->head;
  while (current)
  {
    Node *next = current->next;
    free(current);
    current = next;
  }

  // Free any unused preallocated nodes (for random allocation)
  if (list->preallocated)
  {
    for (size_t i = list->prealloc_used; i < list->prealloc_size; i++)
    {
      free(list->preallocated[i]);
    }
    free(list->preallocated);
  }

  free(list);
}

// Factory function to create linked list
DataStructure create_linkedlist(size_t initial_size, bool random_alloc)
{
  LinkedList *list = malloc(sizeof(LinkedList));
  list->head = NULL;
  list->size = 0;
  list->random_allocation = random_alloc;
  list->preallocated = NULL;
  list->prealloc_size = 0;
  list->prealloc_used = 0;

  // Set up random allocation if requested
  if (random_alloc)
  {
    setup_random_allocation(list, initial_size * 2); // Extra space for insertions
  }

  // Pre-initialize with data (insert at head, so order will be reversed)
  for (size_t i = 0; i < initial_size; i++)
  {
    list_insert(list, 0, (int)(initial_size - 1 - i)); // Insert in reverse to get 0,1,2,3...
  }

  DataStructure ds = {
      .data_structure = list,
      .get = list_get,
      .set = list_set,
      .insert = list_insert,
      .delete = list_delete,
      .destroy = list_destroy,
      .current_size = &list->size};

  return ds;
}
