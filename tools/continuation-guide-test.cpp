// Headless Vulkan runner for the actual continuation-guide sampling shader.
// No Minecraft process, native renderer modifications, WSI, or display input.
#include <vulkan/vulkan.h>
#include <array>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

static void check(VkResult result, const char* operation) {
    if (result != VK_SUCCESS)
        throw std::runtime_error(std::string(operation) + ": VkResult " + std::to_string(result));
}

struct Buffer {
    VkBuffer buffer = VK_NULL_HANDLE;
    VkDeviceMemory memory = VK_NULL_HANDLE;
    void* mapped = nullptr;
    VkDeviceSize bytes = 0;
};

struct Context {
    VkInstance instance = VK_NULL_HANDLE;
    VkPhysicalDevice physical = VK_NULL_HANDLE;
    VkDevice device = VK_NULL_HANDLE;
    VkQueue queue = VK_NULL_HANDLE;
    uint32_t queueFamily = 0;
    VkDescriptorSetLayout setLayout = VK_NULL_HANDLE;
    VkDescriptorPool descriptorPool = VK_NULL_HANDLE;
    VkPipelineLayout pipelineLayout = VK_NULL_HANDLE;
    VkShaderModule shader = VK_NULL_HANDLE;
    VkPipeline pipeline = VK_NULL_HANDLE;
    VkCommandPool commandPool = VK_NULL_HANDLE;
    VkFence fence = VK_NULL_HANDLE;
    std::array<Buffer, 1> buffers{};

    ~Context() {
        if (device) {
            vkDeviceWaitIdle(device);
            if (fence) vkDestroyFence(device, fence, nullptr);
            if (commandPool) vkDestroyCommandPool(device, commandPool, nullptr);
            if (pipeline) vkDestroyPipeline(device, pipeline, nullptr);
            if (shader) vkDestroyShaderModule(device, shader, nullptr);
            if (pipelineLayout) vkDestroyPipelineLayout(device, pipelineLayout, nullptr);
            if (descriptorPool) vkDestroyDescriptorPool(device, descriptorPool, nullptr);
            if (setLayout) vkDestroyDescriptorSetLayout(device, setLayout, nullptr);
            for (auto& b : buffers) {
                if (b.mapped) vkUnmapMemory(device, b.memory);
                if (b.buffer) vkDestroyBuffer(device, b.buffer, nullptr);
                if (b.memory) vkFreeMemory(device, b.memory, nullptr);
            }
            vkDestroyDevice(device, nullptr);
        }
        if (instance) vkDestroyInstance(instance, nullptr);
    }

    void allocate(Buffer& b, VkDeviceSize bytes) {
        b.bytes = bytes;
        VkBufferCreateInfo info{VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO};
        info.size = bytes;
        info.usage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT;
        info.sharingMode = VK_SHARING_MODE_EXCLUSIVE;
        check(vkCreateBuffer(device, &info, nullptr, &b.buffer), "create buffer");
        VkMemoryRequirements required{};
        vkGetBufferMemoryRequirements(device, b.buffer, &required);
        VkPhysicalDeviceMemoryProperties memory{};
        vkGetPhysicalDeviceMemoryProperties(physical, &memory);
        uint32_t type = UINT32_MAX;
        constexpr auto wanted = VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT;
        for (uint32_t i = 0; i < memory.memoryTypeCount; ++i) {
            if ((required.memoryTypeBits & (1u << i)) &&
                (memory.memoryTypes[i].propertyFlags & wanted) == wanted) {
                type = i;
                break;
            }
        }
        if (type == UINT32_MAX) throw std::runtime_error("No coherent host-visible memory type");
        VkMemoryAllocateInfo allocation{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};
        allocation.allocationSize = required.size;
        allocation.memoryTypeIndex = type;
        check(vkAllocateMemory(device, &allocation, nullptr, &b.memory), "allocate memory");
        check(vkBindBufferMemory(device, b.buffer, b.memory, 0), "bind buffer memory");
        check(vkMapMemory(device, b.memory, 0, VK_WHOLE_SIZE, 0, &b.mapped), "map coherent memory");
        std::memset(b.mapped, 0, bytes);

    }
};

int main(int argc, char** argv) try {
    if (argc != 3) {
        std::cerr << "Usage: continuation-guide-test SHADER.spv READBACK.bin\n";
        return 2;
    }
    Context c;
    VkApplicationInfo app{VK_STRUCTURE_TYPE_APPLICATION_INFO};
    app.pApplicationName = "Continuation guide energy check";
    app.apiVersion = VK_API_VERSION_1_2;
    VkInstanceCreateInfo instance{VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO};
    instance.pApplicationInfo = &app;
    check(vkCreateInstance(&instance, nullptr, &c.instance), "create instance");
    uint32_t count = 0;
    check(vkEnumeratePhysicalDevices(c.instance, &count, nullptr), "enumerate GPU count");
    std::vector<VkPhysicalDevice> devices(count);
    check(vkEnumeratePhysicalDevices(c.instance, &count, devices.data()), "enumerate GPUs");
    VkPhysicalDeviceProperties properties{};
    for (auto device : devices) {
        VkPhysicalDeviceProperties p{};
        vkGetPhysicalDeviceProperties(device, &p);
        if (p.vendorID == 0x10de && std::string(p.deviceName).find("5090") != std::string::npos) {
            c.physical = device;
            properties = p;
            break;
        }
    }
    if (!c.physical) throw std::runtime_error("RTX 5090 not found; refusing another GPU");
    vkGetPhysicalDeviceQueueFamilyProperties(c.physical, &count, nullptr);
    std::vector<VkQueueFamilyProperties> families(count);
    vkGetPhysicalDeviceQueueFamilyProperties(c.physical, &count, families.data());
    c.queueFamily = UINT32_MAX;
    for (uint32_t i = 0; i < count; ++i) if (families[i].queueFlags & VK_QUEUE_COMPUTE_BIT) {
        c.queueFamily = i;
        break;
    }
    if (c.queueFamily == UINT32_MAX) throw std::runtime_error("No compute queue");
    float priority = 1;
    VkDeviceQueueCreateInfo queueInfo{VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO};
    queueInfo.queueFamilyIndex = c.queueFamily;
    queueInfo.queueCount = 1;
    queueInfo.pQueuePriorities = &priority;
    VkDeviceCreateInfo deviceInfo{VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO};
    deviceInfo.queueCreateInfoCount = 1;
    deviceInfo.pQueueCreateInfos = &queueInfo;
    check(vkCreateDevice(c.physical, &deviceInfo, nullptr, &c.device), "create compute device");
    vkGetDeviceQueue(c.device, c.queueFamily, 0, &c.queue);
    c.allocate(c.buffers[0], 2048 * 36 * 4 * sizeof(float));

    VkDescriptorSetLayoutBinding binding{0, VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 1, VK_SHADER_STAGE_COMPUTE_BIT, nullptr};
    VkDescriptorSetLayoutCreateInfo setInfo{VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO};
    setInfo.bindingCount = 1;
    setInfo.pBindings = &binding;
    check(vkCreateDescriptorSetLayout(c.device, &setInfo, nullptr, &c.setLayout), "create descriptor layout");
    VkDescriptorPoolSize poolSize{VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 1};
    VkDescriptorPoolCreateInfo poolInfo{VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO};
    poolInfo.maxSets = 1;
    poolInfo.poolSizeCount = 1;
    poolInfo.pPoolSizes = &poolSize;
    check(vkCreateDescriptorPool(c.device, &poolInfo, nullptr, &c.descriptorPool), "create descriptor pool");
    VkDescriptorSetAllocateInfo setAllocation{VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO};
    setAllocation.descriptorPool = c.descriptorPool;
    setAllocation.descriptorSetCount = 1;
    setAllocation.pSetLayouts = &c.setLayout;
    VkDescriptorSet set{};
    check(vkAllocateDescriptorSets(c.device, &setAllocation, &set), "allocate descriptor set");
    VkDescriptorBufferInfo outputInfo{c.buffers[0].buffer, 0, c.buffers[0].bytes};
    VkWriteDescriptorSet write{VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET};
    write.dstSet = set;
    write.dstBinding = 0;
    write.descriptorCount = 1;
    write.descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
    write.pBufferInfo = &outputInfo;
    vkUpdateDescriptorSets(c.device, 1, &write, 0, nullptr);
    VkPipelineLayoutCreateInfo layoutInfo{VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO};
    layoutInfo.setLayoutCount = 1;
    layoutInfo.pSetLayouts = &c.setLayout;
    check(vkCreatePipelineLayout(c.device, &layoutInfo, nullptr, &c.pipelineLayout), "create pipeline layout");
    std::ifstream input(argv[1], std::ios::binary | std::ios::ate);
    if (!input) throw std::runtime_error("Cannot open shader");
    auto size = input.tellg();
    if (size <= 0 || size % 4) throw std::runtime_error("Invalid SPIR-V size");
    std::vector<uint32_t> code(static_cast<size_t>(size) / 4);
    input.seekg(0);
    if (!input.read(reinterpret_cast<char*>(code.data()), size)) throw std::runtime_error("Cannot read shader");
    VkShaderModuleCreateInfo shaderInfo{VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO};
    shaderInfo.codeSize = static_cast<size_t>(size);
    shaderInfo.pCode = code.data();
    check(vkCreateShaderModule(c.device, &shaderInfo, nullptr, &c.shader), "create shader module");
    VkComputePipelineCreateInfo pipelineInfo{VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO};
    pipelineInfo.layout = c.pipelineLayout;
    pipelineInfo.stage.sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;
    pipelineInfo.stage.stage = VK_SHADER_STAGE_COMPUTE_BIT;
    pipelineInfo.stage.module = c.shader;
    pipelineInfo.stage.pName = "main";
    check(vkCreateComputePipelines(c.device, VK_NULL_HANDLE, 1, &pipelineInfo, nullptr, &c.pipeline), "create compute pipeline");
    VkCommandPoolCreateInfo commandPoolInfo{VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO};
    commandPoolInfo.queueFamilyIndex = c.queueFamily;
    check(vkCreateCommandPool(c.device, &commandPoolInfo, nullptr, &c.commandPool), "create command pool");
    VkCommandBufferAllocateInfo commandInfo{VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO};
    commandInfo.commandPool = c.commandPool;
    commandInfo.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY;
    commandInfo.commandBufferCount = 1;
    VkCommandBuffer command{};
    check(vkAllocateCommandBuffers(c.device, &commandInfo, &command), "allocate command buffer");
    VkCommandBufferBeginInfo begin{VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};
    begin.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
    check(vkBeginCommandBuffer(command, &begin), "begin command buffer");
    vkCmdBindPipeline(command, VK_PIPELINE_BIND_POINT_COMPUTE, c.pipeline);
    vkCmdBindDescriptorSets(command, VK_PIPELINE_BIND_POINT_COMPUTE, c.pipelineLayout, 0, 1, &set, 0, nullptr);
    vkCmdDispatch(command, 32, 36, 1);
    VkMemoryBarrier readback{VK_STRUCTURE_TYPE_MEMORY_BARRIER};
    readback.srcAccessMask = VK_ACCESS_SHADER_WRITE_BIT;
    readback.dstAccessMask = VK_ACCESS_HOST_READ_BIT;
    vkCmdPipelineBarrier(command, VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT, VK_PIPELINE_STAGE_HOST_BIT, 0,
                         1, &readback, 0, nullptr, 0, nullptr);
    check(vkEndCommandBuffer(command), "end command buffer");
    VkFenceCreateInfo fenceInfo{VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};
    check(vkCreateFence(c.device, &fenceInfo, nullptr, &c.fence), "create fence");
    VkSubmitInfo submission{VK_STRUCTURE_TYPE_SUBMIT_INFO};
    submission.commandBufferCount = 1;
    submission.pCommandBuffers = &command;
    check(vkQueueSubmit(c.queue, 1, &submission, c.fence), "submit compute test");
    check(vkWaitForFences(c.device, 1, &c.fence, VK_TRUE, 30'000'000'000ULL), "wait for GPU test");

    std::ofstream output(argv[2], std::ios::binary);
    output.write(static_cast<const char*>(c.buffers[0].mapped), c.buffers[0].bytes);
    if (!output) throw std::runtime_error("Cannot write readback");
    std::cout << "{\"gpu\":" << std::quoted(properties.deviceName)
              << ",\"raw_gpu_readback\":true,\"bytes\":" << c.buffers[0].bytes << "}\n";
    return 0;
} catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
}
