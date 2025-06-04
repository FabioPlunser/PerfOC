#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "container_registry.h"

static ContainerFactory *registry_head = NULL;

void register_container(const char *name, const char *description,
                        Container (*create_function)(void))
{
    ContainerFactory *factory = malloc(sizeof(ContainerFactory));
    if (!factory)
    {
        fprintf(stderr, "Failed to allocate memory for container factory\n");
        return;
    }

    factory->name = strdup(name);
    factory->description = description ? strdup(description) : strdup("No description");
    factory->create_function = create_function;
    factory->next = NULL;

    if (!registry_head)
    {
        registry_head = factory;
    }
    else
    {
        ContainerFactory *current = registry_head;
        while (current->next)
        {
            current = current->next;
        }
        current->next = factory;
    }

    printf("Registered container: %s\n", name);
}

Container *create_container_by_name(const char *name)
{
    ContainerFactory *current = registry_head;

    while (current)
    {
        if (strcmp(current->name, name) == 0)
        {
            Container *container = malloc(sizeof(Container));
            if (!container)
                return NULL;

            *container = current->create_function();

            if (!container->data)
            {
                free(container);
                return NULL;
            }

            return container;
        }
        current = current->next;
    }

    return NULL;
}

void list_available_containers(void)
{
    printf("\n**Available Container Types**\n");
    printf("═══════════════════════════════════════════════════════════\n");
    printf("%-25s | %-30s\n", "CONTAINER NAME", "DESCRIPTION");
    printf("─────────────────────────┼────────────────────────────────\n");

    if (!registry_head)
    {
        printf("%-25s | %-30s\n", "No containers", "Registry is empty");
    }
    else
    {
        ContainerFactory *current = registry_head;
        while (current)
        {
            printf("%-25s | %-30s\n",
                   current->name,
                   current->description ? current->description : "No description");
            current = current->next;
        }
    }

    printf("═══════════════════════════════════════════════════════════\n\n");
}

void init_container_registry(void)
{
    printf("Initializing container registry...\n");

    // Forward declarations for container creators
    extern Container create_array_container(void);
    extern Container create_linkedlist_sequential(void);
    extern Container create_linkedlist_random(void);
    extern Container create_unrolled_linkedlist_8(void);
    extern Container create_unrolled_linkedlist_16(void);
    extern Container create_unrolled_linkedlist_32(void);
    extern Container create_unrolled_linkedlist_64(void);
    extern Container create_unrolled_linkedlist_128(void);
    extern Container create_unrolled_linkedlist_256(void);
    extern Container create_tiered_array_8(void);
    extern Container create_tiered_array_16(void);
    extern Container create_tiered_array_32(void);
    extern Container create_tiered_array_64(void);
    extern Container create_tiered_array_128(void);
    extern Container create_tiered_array_256(void);

    // Register all available containers
    register_container("array",
                       "Static array implementation",
                       create_array_container);

    register_container("linkedlist_seq",
                       "Sequential linked list implementation",
                       create_linkedlist_sequential);

    register_container("linkedlist_rand",
                       "Random allocation linked list",
                       create_linkedlist_random);

    register_container("unrolled_linkedlist_8",
                       "Unrolled linked list with chunked storage (8 elements per chunk)",
                       create_unrolled_linkedlist_8);

    register_container("unrolled_linkedlist_16",
                       "Unrolled linked list with chunked storage (16 elements per chunk)",
                       create_unrolled_linkedlist_16);

    register_container("unrolled_linkedlist_32",
                       "Unrolled linked list with chunked storage (32 elements per chunk)",
                       create_unrolled_linkedlist_32);

    register_container("unrolled_linkedlist_64",
                       "Unrolled linked list with chunked storage (64 elements per chunk)",
                       create_unrolled_linkedlist_64);

    register_container("unrolled_linkedlist_128",
                       "Unrolled linked list with chunked storage (128 elements per chunk)",
                       create_unrolled_linkedlist_128);

    register_container("unrolled_linkedlist_256",
                       "Unrolled linked list with chunked storage (256 elements per chunk)",
                       create_unrolled_linkedlist_256);

    register_container("tiered_array_8",
                       "Tiered array with 8 elements per chunk",
                       create_tiered_array_8);

    register_container("tiered_array_16",
                       "Tiered array with 16 elements per chunk",
                       create_tiered_array_16);

    register_container("tiered_array_32",
                       "Tiered array with 32 elements per chunk",
                       create_tiered_array_32);

    register_container("tiered_array_64",
                       "Tiered array with 64 elements per chunk",
                       create_tiered_array_64);

    register_container("tiered_array_128",
                       "Tiered array with 128 elements per chunk",
                       create_tiered_array_128);

    register_container("tiered_array_256",
                       "Tiered array with 256 elements per chunk",
                       create_tiered_array_256);

    printf("Registry initialization complete!\n\n");
}

void cleanup_container_registry(void)
{
    printf("Cleaning up container registry...\n");

    ContainerFactory *current = registry_head;
    int count = 0;

    while (current)
    {
        ContainerFactory *next = current->next;

        free((void *)current->name);
        if (current->description)
        {
            free((void *)current->description);
        }

        free(current);
        current = next;
        count++;
    }

    registry_head = NULL;
    printf("Cleaned up %d container registrations\n", count);
}