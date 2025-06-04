#ifndef CONTAINER_REGISTRY_H
#define CONTAINER_REGISTRY_H

#include "benchmark.h"

typedef struct ContainerFactory
{
    const char *name;
    const char *description;
    Container (*create_function)(void);
    struct ContainerFactory *next;
} ContainerFactory;

void register_container(const char *name, const char *description,
                        Container (*create_function)(void));
Container *create_container_by_name(const char *name);
void list_available_containers(void);
void init_container_registry(void);
void cleanup_container_registry(void);

#endif